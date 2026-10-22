"""Offline mock provider: deterministic, free, never touches the network.

It answers from the task files themselves, so the whole paid code path (reserve,
dispatch, settle, score, report) runs in tests and CI with no API key.

Models:
  oracle    returns the gold answer as bare JSON / the gold class. Scores 100%.
  fenced    the oracle answer wrapped in a ```json code fence (rent) - exercises the
            parser's single-fence tolerance. Scores 100%.
  baseline  a naive model: every listed bed group comes back with available=0 and no
            concession; every permit is "commercial" (the majority class). Shows how
            the scorer separates hallucinated zeros from honest nulls.

Token counts are a chars/4 approximation and costs use synthetic price rows; neither
is a real measurement.
"""
from __future__ import annotations

import json
from functools import lru_cache

from llm_evals import providers, tasks

MODELS = ('oracle', 'fenced', 'baseline')


@lru_cache(maxsize=1)
def _answers() -> dict:
    """user message -> (task, gold) for every bundled case."""
    out = {}
    for task in tasks.TASK_NAMES:
        _, cases = tasks.load_cases(task)
        for case in cases:
            out[case["user"]] = (task, case["gold"])
    return out


def _gold_json(gold: dict) -> dict:
    return {"units": gold["units"], "concession_weeks": gold.get("concession_weeks")}


def answer(model: str, task: str, gold: dict) -> str:
    if model not in MODELS:
        raise ValueError(f'Unknown mock model {model!r}; choose from {", ".join(MODELS)}')
    if task == "permits":
        return "commercial" if model == "baseline" else gold["expected_class"]
    payload = _gold_json(gold)
    if model == "baseline":
        payload = {"units": [dict(u, available=0) for u in gold["units"]],
                   "concession_weeks": None}
    text = json.dumps(payload)
    return f"```json\n{text}\n```" if model == "fenced" else text


def complete(model, system, user, max_tokens) -> providers.Completion:
    hit = _answers().get(user)
    if hit is None:
        # An unknown case gets an honest abstention rather than an invented answer.
        text = "unknown"
    else:
        text = answer(model, *hit)
    return providers.Completion(text=text,
                                input_tokens=(len(system) + len(user)) // 4,
                                output_tokens=max(1, len(text) // 4),
                                cache_read_tokens=0, cache_write_tokens=0,
                                latency_ms=0, finish_reason='stop',
                                response_id=f'mock-{model}')
