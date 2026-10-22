import copy
import json
import tempfile
import unittest

from llm_evals import ROOT, run, score


class ScoringRegressions(unittest.TestCase):
    def setUp(self):
        self.gold = json.loads((ROOT / 'tasks/rent_extraction/gold/avail_sandy_springs.json').read_text())
        self.pred = {k: copy.deepcopy(self.gold[k]) for k in ('units', 'concession_weeks')}

    def test_coming_soon_is_graded(self):
        self.pred['units'][0]['coming_soon'] = 999
        self.assertFalse(score.score_rent('sample', self.gold, self.pred).strict)

    def test_shape_duplicates_and_boolean_are_invalid(self):
        invalid = [[], {}, {'units': [], 'concession_weeks': False}]
        duplicate = copy.deepcopy(self.pred)
        duplicate['units'].append(copy.deepcopy(duplicate['units'][0]))
        invalid.append(duplicate)
        boolean = copy.deepcopy(self.pred)
        boolean['units'][0]['available'] = True
        invalid.append(boolean)
        for pred in invalid:
            with self.subTest(pred_type=type(pred).__name__):
                result = score.score_rent('sample', self.gold, pred)
                self.assertFalse(result.strict)
                self.assertTrue(result.parse_error)

    def test_invalid_output_counts_all_expected_fields(self):
        good = score.score_rent('sample', self.gold, self.pred)
        bad = score.score_rent('sample', self.gold, None, 'invalid JSON')
        self.assertEqual(bad.n_total, good.n_total)
        self.assertEqual(bad.n_pass, 0)

    def test_failed_requests_in_operational_denominator_and_cost(self):
        cases = [dict(seed=0, correct=True, cost_usd=.001),
                 dict(seed=0, error='API error', cost_usd=.002)]
        report = run.render_report('test', {('permits', 'model'): {'cases': cases}}, 1)
        self.assertIn('50.0%', report)
        self.assertIn('$0.0030', report)
        self.assertNotIn('100.0%', report)

    def test_nonsense_cannot_pass_unknown_gold(self):
        self.assertNotEqual(score.normalize_class('totally invalid'), 'unknown')


class ParseFences(unittest.TestCase):
    """The production extractor strips one code fence before json.loads. Haiku 4.5
    wraps every rent reply in ```json ... ``` despite the prompt's "no code fences",
    so a fence-rejecting parser scored the production model 0/30 for a reason
    production never sees (the 2026-09-18 Haiku run, before this fix)."""

    def test_json_code_fence_is_stripped_like_production(self):
        fenced = '```json\n{"units": [], "concession_weeks": null}\n```'
        self.assertEqual(run.parse_json(fenced), ({'units': [], 'concession_weeks': None}, ''))

    def test_bare_fence_without_language_tag_is_stripped(self):
        self.assertEqual(run.parse_json('```\n{"a": 1}\n```'), ({'a': 1}, ''))

    def test_prose_around_json_still_fails(self):
        self.assertIsNone(run.parse_json('Here you go: {"a": 1}')[0])


class AlternateCasesFile(unittest.TestCase):
    """--cases-json lets a permits run take a sweep file (goldens.json shape) whose
    expected_class is another model's stored label; the default path is untouched."""

    def test_permits_cases_json_is_used_and_meta_passes_through(self):
        rows = [{"id": 1, "row_id": "99", "input": {"facility_name": "X Residence", "city": "MESA"},
                 "expected_class": "single_family", "stratum": "single_family",
                 "label_note": "production label", "meta": {"dwelling_type": "single_family", "rule": None}}]
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(rows, f)
        sysp, cases = run.load_cases('permits', 0, f.name)
        self.assertEqual([c['id'] for c in cases], ['99'])
        self.assertEqual(cases[0]['gold']['meta']['dwelling_type'], 'single_family')
        self.assertIn('"facility_name": "X Residence"', cases[0]['user'])
        _, default_cases = run.load_cases('permits', 0)
        self.assertEqual(len(default_cases), 65)
