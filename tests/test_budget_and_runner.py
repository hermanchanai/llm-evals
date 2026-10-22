import concurrent.futures
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest

from llm_evals import ROOT, budget, pricing, providers, run
from llm_evals import fixtures as build_fixtures

# Stand-in credential value: tests never send a request anywhere.
PLACEHOLDER = 'offline-test-only'


def concurrent_reserve(args):
    path, amount = args
    try:
        return budget.Budget(path, '.010000').reserve(amount, 'test', 100, 10)
    except budget.BudgetError:
        return None


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'budget' / 'ledger.json'
        self.ledger = budget.Budget(self.path, '.010000')
        self.ledger.initialize()

    def tearDown(self):
        self.temp.cleanup()

    def test_restart_retains_crash_reservation(self):
        self.ledger.reserve(9000, 'test', 100, 10)
        restarted = budget.Budget(self.path, '.010000')
        with self.assertRaises(budget.BudgetError):
            restarted.reserve(1001, 'test', 100, 10)
        restarted.reserve(1000, 'test', 100, 10)

    def test_concurrent_processes_cannot_overspend(self):
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
            ids = list(executor.map(concurrent_reserve, [(self.path, 6000)] * 8))
        self.assertEqual(sum(x is not None for x in ids), 1)
        self.assertEqual(self.ledger.used(self.ledger.check()), 6000)

    def test_missing_corrupt_changed_ceiling_and_reinitialization_block(self):
        with self.assertRaises(budget.BudgetError):
            self.ledger.initialize()
        with self.assertRaises(budget.BudgetError):
            budget.Budget(self.path, '.020000').check()
        self.path.write_text('invalid')
        with self.assertRaises(budget.BudgetError):
            self.ledger.check()
        self.path.unlink()
        with self.assertRaises(budget.BudgetError):
            self.ledger.check()

    def test_optimized_python_cannot_bypass_validation(self):
        script = ('import sys; sys.path.insert(0, sys.argv[1]); from llm_evals import budget; '
                  'budget.Budget(sys.argv[2], ".020000").check()')
        result = subprocess.run([sys.executable, '-O', '-c', script, str(ROOT), str(self.path)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BudgetError', result.stderr)

    def test_daily_boundary_and_dst_pending_carry(self):
        moments = [datetime(2026, 3, 8, 7, 59, tzinfo=timezone.utc),
                   datetime(2026, 3, 8, 8, 0, tzinfo=timezone.utc),
                   datetime(2026, 3, 8, 10, 1, tzinfo=timezone.utc)]
        clock = [moments[0]]
        ledger = budget.Budget(self.path, '.010000', lambda: clock[0])
        rid = ledger.reserve(4000, 'test', 100, 10)
        ledger.settle(rid, 1000, 50, 3)
        ledger.reserve(6000, 'test', 100, 10)
        self.assertEqual(ledger.day(), '2026-03-07')
        clock[0] = moments[1]
        self.assertEqual(ledger.day(), '2026-03-08')
        self.assertEqual(ledger.used(ledger.check()), 6000)
        clock[0] = moments[2]
        self.assertEqual(ledger.day(), '2026-03-08')
        self.assertEqual(ledger.used(ledger.check()), 6000)
        # Fall-back repeats 01:30, not midnight or a new budget day.
        for hour in (8, 9):
            clock[0] = datetime(2026, 11, 1, hour, 30, tzinfo=timezone.utc)
            self.assertEqual(ledger.day(), '2026-11-01')
            self.assertEqual(ledger.used(ledger.check()), 6000)

    def test_unknown_and_out_of_bound_usage_never_release(self):
        rid = self.ledger.reserve(6000, 'test', 100, 10)
        with self.assertRaises(budget.BudgetError):
            self.ledger.settle(rid, None, 20, 1)
        self.assertEqual(self.ledger.used(self.ledger.check()), 6000)
        with self.assertRaises(budget.BudgetError):
            self.ledger.settle(rid, 1000, 101, 1)
        with self.assertRaises(budget.BudgetError):
            self.ledger.check()
        with self.assertRaises(budget.BudgetError):
            self.ledger.reserve(1, 'test', 1, 1)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'ledger.json'
        self.ledger = budget.Budget(self.path, '.100000')
        self.ledger.initialize()
        self.case = dict(id='test', user='test', gold={'expected_class': 'unknown'})

    def tearDown(self):
        self.temp.cleanup()

    def call(self, **kwargs):
        return run.attempt('permits', self.case, 'openai', 'gpt-5.6-luna', 'system', 10,
                           kwargs.get('ledger', self.ledger))

    def test_exhausted_budget_has_zero_provider_calls(self):
        self.ledger.reserve(100000, 'test', 100, 10)
        with patch.object(providers, 'complete') as api:
            with self.assertRaises(budget.BudgetError):
                self.call()
            api.assert_not_called()

    def test_all_provider_preflight_precedes_any_spend(self):
        argv = ['run', '--models', 'anthropic:claude-haiku-4-5,openai:gpt-5.6-luna',
                '--daily-limit-usd', '.100000', '--limit', '1', '--repetitions', '1']
        with patch.object(sys, 'argv', argv), patch.object(budget, 'default_path', return_value=self.path), \
                patch.dict(os.environ, {'ANTHROPIC_API_KEY': PLACEHOLDER}, clear=True), \
                patch.object(providers, 'complete') as api, patch('sys.stderr', io.StringIO()):
            self.assertEqual(run.main(), 2)
            api.assert_not_called()
        self.assertEqual(self.ledger.used(self.ledger.check()), 0)

    def test_unknown_price_has_zero_provider_calls(self):
        with patch.dict(pricing.PRICING, {}, clear=True), patch.object(providers, 'complete') as api:
            with self.assertRaises(pricing.UnknownPricing):
                self.call()
            api.assert_not_called()

    def test_request_error_preserves_hold_and_halts(self):
        with patch.object(providers, 'complete', side_effect=TimeoutError('secret payload')) as api:
            rec = self.call()
        self.assertEqual(api.call_count, 1)
        self.assertTrue(rec['halt'])
        self.assertNotIn('secret payload', rec['error'])
        self.assertGreater(self.ledger.used(self.ledger.check()), 0)

    def test_missing_cache_usage_halts_and_withholds_cost_ranking(self):
        response = providers.Completion('unknown', 10, 1, cache_write_tokens=None)
        with patch.object(providers, 'complete', return_value=response):
            rec = self.call()
        self.assertTrue(rec['halt'])
        self.assertIsNone(rec['cost_usd'])
        self.assertGreater(self.ledger.used(self.ledger.check()), 0)
        report = run.render_report('test', {('permits', 'luna'): {'cases': [rec]}}, 1)
        self.assertIn('(partial)', report)

    def test_rejected_settlement_keeps_cost_unknown_and_suppresses_rankings(self):
        responses = [providers.Completion('unknown', 10, 1),
                     providers.Completion('unknown', 10, 11)]
        with patch.object(providers, 'complete', side_effect=responses):
            good = self.call()
            rejected = self.call()
        self.assertTrue(good['correct'])
        self.assertTrue(rejected['halt'])
        self.assertIsNone(rejected['cost_usd'])
        report = run.render_report('test', {('permits', 'luna'): {'cases': [good, rejected]}}, 1)
        cells = next(line for line in report.splitlines() if line.startswith('| luna |')).split('|')
        self.assertIn('(partial)', cells[9])
        self.assertEqual(cells[10].strip(), '1')  # unknown costs
        self.assertEqual(cells[11].strip(), '-')  # cost per attempted record
        self.assertEqual(cells[12].strip(), '-')  # cost per correct record
        with self.assertRaises(budget.BudgetError):
            self.ledger.check()

    def test_truncation_keeps_cost_and_fails(self):
        response = providers.Completion('unknown', 10, 10, finish_reason='length')
        with patch.object(providers, 'complete', return_value=response):
            rec = self.call()
        self.assertFalse(rec['correct'])
        self.assertFalse(rec['operational_success'])
        self.assertGreater(rec['cost_usd'], 0)
        self.assertFalse(rec.get('halt', False))

    def test_scoring_exception_keeps_cost(self):
        response = providers.Completion('unknown', 10, 1)
        with patch.object(providers, 'complete', return_value=response), patch.object(run, 'evaluate', side_effect=ValueError):
            rec = self.call()
        self.assertGreater(rec['cost_usd'], 0)
        self.assertIn('scoring failed', rec['error'])

    def test_cache_cost_and_reservation_bound(self):
        self.assertAlmostEqual(pricing.cost_usd('gpt-5.6-luna', 1000, 100, 200, 300), .000299)
        amount, bound = pricing.reservation('openai', 'gpt-5.6-luna', 'é', 'x', 4096)
        self.assertEqual(bound, 1027)
        for cached, written in [(0, 0), (bound, 0), (0, bound)]:
            self.assertGreaterEqual(amount, pricing.to_microusd(pricing.cost_decimal('gpt-5.6-luna', bound, 4096, cached, written)))
        for counts in [(10, 1, 11, 0), (10, True, 0, 0), (10, 1, None, 0)]:
            with self.assertRaises(pricing.UnknownUsage):
                pricing.cost_usd('gpt-5.6-luna', *counts)

    def test_json_duplicate_keys_nan_and_wrapped_text_fail(self):
        for text in ('{"units":[],"units":[]}', '{"x":NaN}', 'answer: {"x":1}'):
            self.assertIsNone(run.parse_json(text)[0])


class ProviderTests(unittest.TestCase):
    def test_luna_parameters_and_usage(self):
        response = NS(id='test', usage=NS(prompt_tokens=100, completion_tokens=20,
                                        prompt_tokens_details=NS(cached_tokens=30, cache_write_tokens=40)),
                      choices=[NS(finish_reason='stop', message=NS(content='unknown', refusal=None))])
        with patch.dict(os.environ, {'OPENAI_API_KEY': PLACEHOLDER}), patch.dict(sys.modules, {'openai': NS(OpenAI=unittest.mock.Mock())}):
            import openai
            openai.OpenAI.return_value.chat.completions.create.return_value = response
            result = providers._openai('gpt-5.6-luna', 'sys', 'user', 4096)
            init = openai.OpenAI.call_args.kwargs
            call = openai.OpenAI.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(init['max_retries'], 0)
        self.assertEqual(init['timeout'], 60)
        self.assertEqual(init['base_url'], 'https://api.openai.com/v1')
        self.assertEqual(call['reasoning_effort'], 'none')
        self.assertEqual(call['service_tier'], 'default')
        self.assertEqual(call['max_completion_tokens'], 4096)
        self.assertEqual(call['temperature'], 0)
        self.assertNotIn('tools', call)
        self.assertNotIn('response_format', call)
        self.assertEqual((result.input_tokens, result.cache_read_tokens, result.cache_write_tokens), (100,30,40))

    def test_anthropic_input_normalization(self):
        response = NS(id='test', stop_reason='end_turn', content=[NS(type='text', text='unknown')],
                      usage=NS(input_tokens=100, output_tokens=20, cache_read_input_tokens=30, cache_creation_input_tokens=40))
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': PLACEHOLDER}), patch.dict(sys.modules, {'anthropic': NS(Anthropic=unittest.mock.Mock())}):
            import anthropic
            anthropic.Anthropic.return_value.messages.create.return_value = response
            result = providers._anthropic('claude-haiku-4-5', 'sys', 'user', 10)
            init = anthropic.Anthropic.call_args.kwargs
        self.assertEqual(result.input_tokens, 170)
        self.assertEqual(init['max_retries'], 0)
        self.assertEqual(init['base_url'], 'https://api.anthropic.com')


class SDKWireTests(unittest.TestCase):
    """Real pinned SDKs over an in-memory transport: no socket is opened.
    Skipped when the SDKs from requirements.txt are not installed."""

    def test_real_sdk_serializes_luna_request_without_network(self):
        httpx2 = pytest.importorskip('httpx2')
        openai = pytest.importorskip('openai')
        calls = []
        def respond(request):
            calls.append(json.loads(request.content))
            return httpx2.Response(200, json={
                'id': 'offline', 'object': 'chat.completion', 'created': 0,
                'model': 'gpt-5.6-luna',
                'choices': [{'index': 0, 'finish_reason': 'stop',
                             'message': {'role': 'assistant', 'content': 'unknown'}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 1, 'total_tokens': 101,
                          'prompt_tokens_details': {'cached_tokens': 10, 'cache_write_tokens': 20}}})
        original = openai.OpenAI
        with httpx2.Client(transport=httpx2.MockTransport(respond)) as http:
            with patch.dict(os.environ, {'OPENAI_API_KEY': PLACEHOLDER}), \
                    patch.object(openai, 'OpenAI', side_effect=lambda **kw: original(**kw, http_client=http)):
                result = providers._openai('gpt-5.6-luna', 'sys', 'user', 10)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['max_completion_tokens'], 10)
        self.assertEqual(calls[0]['reasoning_effort'], 'none')
        self.assertEqual(result.cache_write_tokens, 20)

    def test_real_sdk_serializes_haiku_temperature_and_usage(self):
        httpx2 = pytest.importorskip('httpx2')
        anthropic = pytest.importorskip('anthropic')
        calls = []
        def respond(request):
            calls.append(json.loads(request.content))
            return httpx2.Response(200, json={
                'id': 'offline', 'type': 'message', 'role': 'assistant',
                'model': 'claude-haiku-4-5', 'stop_reason': 'end_turn', 'stop_sequence': None,
                'content': [{'type': 'text', 'text': 'unknown'}],
                'usage': {'input_tokens': 100, 'output_tokens': 1,
                          'cache_read_input_tokens': 10, 'cache_creation_input_tokens': 20}})
        original = anthropic.Anthropic
        with httpx2.Client(transport=httpx2.MockTransport(respond)) as http:
            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': PLACEHOLDER}), \
                    patch.object(anthropic, 'Anthropic', side_effect=lambda **kw: original(**kw, http_client=http)):
                result = providers._anthropic('claude-haiku-4-5', 'sys', 'user', 10)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['temperature'], 0)
        self.assertEqual(calls[0]['service_tier'], 'standard_only')
        self.assertEqual((result.input_tokens, result.cache_write_tokens), (130, 20))

    def test_real_sdk_timeout_does_not_retry(self):
        httpx2 = pytest.importorskip('httpx2')
        openai = pytest.importorskip('openai')
        calls = []
        def timeout(request):
            calls.append(request)
            raise httpx2.ReadTimeout('offline simulated timeout', request=request)
        original = openai.OpenAI
        with httpx2.Client(transport=httpx2.MockTransport(timeout)) as http:
            with patch.dict(os.environ, {'OPENAI_API_KEY': PLACEHOLDER}), \
                    patch.object(openai, 'OpenAI', side_effect=lambda **kw: original(**kw, http_client=http)):
                with self.assertRaises(openai.APITimeoutError):
                    providers._openai('gpt-5.6-luna', 'sys', 'user', 10)
        self.assertEqual(len(calls), 1)


class FixtureTests(unittest.TestCase):
    def test_verify_checks_saved_text(self):
        with tempfile.TemporaryDirectory() as temp:
            with redirect_stdout(io.StringIO()), patch.object(build_fixtures, 'FIX', Path(temp)), patch.object(sys, 'argv', ['verify', '--verify']):
                self.assertEqual(build_fixtures.main(), 1)


if __name__ == '__main__':
    unittest.main()
