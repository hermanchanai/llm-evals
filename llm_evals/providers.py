"""Provider adapters: one request per call, standard tier, no tools, text only.

Counts are normalized so input_tokens includes cache reads and writes.
Missing or ambiguous usage is kept as None and can never release a budget reservation.

Providers:
  anthropic  Messages API (needs ANTHROPIC_API_KEY and the pinned SDK)
  openai     Chat Completions (needs OPENAI_API_KEY and the pinned SDK)
  mock       offline, deterministic, free; see llm_evals/mock.py
"""
from __future__ import annotations

import importlib
import os
import time
from dataclasses import dataclass


@dataclass
class Completion:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None = 0
    cache_write_tokens: int | None = 0
    latency_ms: int = 0
    finish_reason: str = 'stop'
    refusal: bool = False
    response_id: str | None = None


def anthropic_sampling(model):
    """Per-model determinism settings, sent through extra_body.

    Haiku 4.5 takes temperature=0 (the pinned SDK no longer has a named argument for it).
    Haiku 5.5 rejects any non-default sampling value and thinks by default, so it gets
    no temperature and thinking disabled.
    """
    if model.startswith('claude-haiku-5-5'):
        return {'thinking': {'type': 'disabled'}}
    return {'temperature': 0}


def _anthropic(model, system, user, max_tokens):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'], max_retries=0, timeout=120.0,
                       base_url='https://api.anthropic.com')
    t0 = time.monotonic()
    m = client.messages.create(model=model, max_tokens=max_tokens,
                               extra_body=anthropic_sampling(model),
                               service_tier="standard_only", system=system,
                               messages=[{'role': 'user', 'content': user}])
    u = m.usage
    # No cache_control is sent; Anthropic omits these optional fields when unused.
    read = getattr(u, 'cache_read_input_tokens', None) or 0
    write = getattr(u, 'cache_creation_input_tokens', None) or 0
    ordinary = getattr(u, 'input_tokens', None)
    total = ordinary + read + write if type(ordinary) is int else None
    return Completion(text=''.join(b.text for b in m.content if getattr(b, 'type', '') == 'text'),
                      input_tokens=total, output_tokens=getattr(u, 'output_tokens', None),
                      cache_read_tokens=read, cache_write_tokens=write,
                      latency_ms=int((time.monotonic()-t0)*1000),
                      finish_reason=m.stop_reason, response_id=m.id)


def _openai(model, system, user, max_tokens):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], max_retries=0, timeout=60.0,
                    base_url='https://api.openai.com/v1')
    t0 = time.monotonic()
    r = client.chat.completions.create(
        model=model, max_completion_tokens=max_tokens, temperature=0,
        reasoning_effort='none', service_tier='default',
        messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}])
    u = r.usage
    details = getattr(u, 'prompt_tokens_details', None)
    # Cache writes are billable on this model family. Missing details are NOT zero usage.
    choice = r.choices[0] if r.choices else None
    return Completion(text=(choice.message.content or '') if choice else '',
                      input_tokens=getattr(u, 'prompt_tokens', None),
                      output_tokens=getattr(u, 'completion_tokens', None),
                      cache_read_tokens=getattr(details, 'cached_tokens', None),
                      cache_write_tokens=getattr(details, 'cache_write_tokens', None),
                      latency_ms=int((time.monotonic()-t0)*1000),
                      finish_reason=choice.finish_reason if choice else 'missing_choice',
                      refusal=bool(getattr(choice.message, 'refusal', None)) if choice else False,
                      response_id=r.id)


def _mock(model, system, user, max_tokens):
    from llm_evals import mock
    return mock.complete(model, system, user, max_tokens)


PROVIDERS = {'anthropic': _anthropic, 'openai': _openai, 'mock': _mock}
KEY_NAMES = {'openai': 'OPENAI_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY'}


def complete(provider, model, system, user, max_tokens):
    if provider not in PROVIDERS:
        raise ValueError('Unsupported provider')
    return PROVIDERS[provider](model, system, user, max_tokens)


def preflight(provider):
    """Network-free checks for every selected provider before the first reservation."""
    if provider not in PROVIDERS:
        raise ValueError('Unsupported provider')
    if provider == 'mock':
        return
    key_name = KEY_NAMES[provider]
    if not os.environ.get(key_name, '').strip():
        raise ValueError(f'Missing {key_name}; no request made')
    try:
        importlib.import_module(provider)
    except ImportError:
        raise ValueError(f'Missing {provider} SDK; install requirements.txt') from None
