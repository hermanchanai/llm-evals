"""Verified standard-tier USD per million tokens; normalized usage is disjoint.

input_tokens includes cache reads AND writes, unlike Anthropic's native usage.
Short-context only: the spending guard rejects inputs outside its verified range.
"""
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal


class UnknownPricing(ValueError):
    pass


class UnknownUsage(ValueError):
    pass


@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float
    cache_write_per_mtok: float
    verified: str


PRICING = {
    'claude-haiku-4-5': ModelPricing(1.0, 5.0, .10, 1.25, '2026-09-18'),
    'claude-haiku-4-5-20251001': ModelPricing(1.0, 5.0, .10, 1.25, '2026-09-18'),
    'claude-sonnet-4-6': ModelPricing(3.0, 15.0, .30, 3.75, '2026-05-19'),
    'claude-sonnet-4-5': ModelPricing(3.0, 15.0, .30, 3.75, '2026-05-19'),
    'claude-opus-4-7': ModelPricing(15.0, 75.0, 1.50, 18.75, '2026-05-19'),
    'claude-opus-4-6': ModelPricing(15.0, 75.0, 1.50, 18.75, '2026-05-19'),
    # https://platform.claude.com/docs/en/about-claude/pricing (2026-10-18), prompts <=100K
    # tokens. Over 100K the whole request bills at 5x; reservation() rejects that range.
    'claude-haiku-5-5': ModelPricing(.10, .50, .01, .125, '2026-10-18'),
    # https://developers.openai.com/api/docs/pricing (2026-09-18)
    'gpt-5.6-luna': ModelPricing(.20, 1.20, .02, .25, '2026-09-18'),
    # https://developers.openai.com/api/docs/pricing (2026-10-18), short context <=272K.
    'gpt-6-luna': ModelPricing(.10, .50, .01, .125, '2026-10-18'),
    # Offline mock models (llm_evals/mock.py). Synthetic rates so the ledger and cost
    # columns are exercised end to end; no money is involved.
    'oracle': ModelPricing(1.0, 5.0, .10, 1.25, 'synthetic'),
    'fenced': ModelPricing(1.0, 5.0, .10, 1.25, 'synthetic'),
    'baseline': ModelPricing(1.0, 5.0, .10, 1.25, 'synthetic'),
}

# A price row alone does not authorize a new provider/model's billing semantics.
GUARDED_MODELS = {
    ('openai', 'gpt-5.6-luna'),
    ('openai', 'gpt-6-luna'),
    ('anthropic', 'claude-haiku-4-5'),
    ('anthropic', 'claude-haiku-4-5-20251001'),
    ('anthropic', 'claude-haiku-5-5'),
    ('mock', 'oracle'),
    ('mock', 'fenced'),
    ('mock', 'baseline'),
}

def price(model):
    p = PRICING.get(model)
    if p is None:
        raise UnknownPricing(f'No verified price row for {model!r}')
    rates = (p.input_per_mtok, p.output_per_mtok, p.cache_read_per_mtok, p.cache_write_per_mtok)
    if not p.verified or any(not Decimal(str(v)).is_finite() or v < 0 for v in rates):
        raise UnknownPricing('Invalid price row')
    return p


def validate_usage(input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0):
    counts = (input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)
    if any(type(v) is not int or v < 0 for v in counts):
        raise UnknownUsage('Missing or invalid token usage')
    if cache_read_tokens + cache_write_tokens > input_tokens:
        raise UnknownUsage('Cache counts exceed total input')


def cost_decimal(model, input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0):
    validate_usage(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)
    p = price(model)
    return (Decimal(input_tokens-cache_read_tokens-cache_write_tokens)*Decimal(str(p.input_per_mtok))
            + Decimal(output_tokens)*Decimal(str(p.output_per_mtok))
            + Decimal(cache_read_tokens)*Decimal(str(p.cache_read_per_mtok))
            + Decimal(cache_write_tokens)*Decimal(str(p.cache_write_per_mtok))) / 1_000_000


def cost_usd(model, input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0):
    return float(cost_decimal(model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens))


def to_microusd(value):
    """Round up for the ledger, never down. Reports retain exact reported cost."""
    value = Decimal(str(value))
    if not value.is_finite() or value < 0:
        raise UnknownUsage('Invalid cost')
    return int((value * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def reservation(provider, model, system, user, max_tokens):
    if (provider, model) not in GUARDED_MODELS:
        raise UnknownPricing('Provider/model has no verified spend-bound policy')
    if type(max_tokens) is not int or not 1 <= max_tokens <= 4096:
        raise UnknownUsage('Output bound must be 1..4096 tokens')
    # Known text-only tokenizers cannot produce more text tokens than UTF-8 bytes.
    # 1,024 extra tokens conservatively cover these two fixed message envelopes.
    input_bound = len(system.encode('utf-8')) + len(user.encode('utf-8')) + 1024
    return _bounded(model, input_bound, max_tokens)


def _bounded(model, input_bound, max_tokens):
    # Also keeps Haiku 5.5 below its 100K-token higher-price threshold.
    if input_bound + max_tokens > 100_000:
        raise UnknownUsage('Request outside verified short-context reservation policy')
    p = price(model)
    # Reserve ordinary input PLUS cache-write rate, even though documented Luna
    # writes replace ordinary input billing. This also covers accounting uncertainty.
    input_rate = max(Decimal(str(p.input_per_mtok)) + Decimal(str(p.cache_write_per_mtok)),
                     Decimal(str(p.cache_read_per_mtok)))
    bound = (input_bound*input_rate + max_tokens*Decimal(str(p.output_per_mtok))) / 1_000_000
    return to_microusd(bound), input_bound
