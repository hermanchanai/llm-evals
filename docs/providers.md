# Providers, pricing and the spending guard

## Running live

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # add a key for each provider you call
.venv/bin/python -m llm_evals.run --dry-run --models openai:gpt-5.6-luna,anthropic:claude-haiku-4-5
```

Dry-run is free and needs no key. Its token estimate is chars/4 and is a planning
number, not a spending bound.

Paid calls need a daily ceiling that you choose. Nothing in the repo picks one for you:

```bash
.venv/bin/python -m llm_evals.budget init   --daily-limit-usd "$DAILY_USD"
.venv/bin/python -m llm_evals.run --task rent --limit 1 --repetitions 1 \
  --models openai:gpt-5.6-luna --daily-limit-usd "$DAILY_USD"
```

Start with one clean case (`avail_sandy_springs` sorts first), inspect the output and
the usage, then run the full comparison.

## The ledger

The ledger lives in the git common directory (`<git dir>/llm-evals-budget/ledger.json`),
so every worktree of a clone shares it. It is a local runner ceiling, not a provider-side
cap: it cannot govern other programs or other clones using the same key, so also set the
provider's own project limit.

- Before each request a process lock records a reservation: UTF-8 input bytes plus 1,024
  framing tokens, the full output cap, and input priced at ordinary plus cache-write rate.
- Complete reported usage settles the entry at the real cost. Missing usage, a timeout, an
  API error or a crash keeps the reservation; any request error halts the run with no retry.
- Usage above the reservation blocks the ledger. Initialization refuses existing state, and a
  changed ceiling or a corrupt file blocks calls. Do not delete or hand-edit the ledger to
  clear spending.
- Days roll over at midnight America/Los_Angeles; unresolved reservations count on every
  later day until settled.

Mock-only runs (`--models mock:...`) use a throwaway ledger with a synthetic ceiling.

## Adapter contract

`llm_evals/providers.py` has one function per provider. Each makes one request with SDK
retries off, a fixed official endpoint, a finite timeout, the standard billing tier, and no
tools or JSON mode, and returns a `Completion`: reply text, finish/refusal status, latency,
response ID and token counts.

- `input_tokens` is normalized to include cache reads and writes. OpenAI's `prompt_tokens`
  already does; Anthropic's native `input_tokens` does not, so the adapter adds them.
- Missing cache-write usage is unknown, never zero, and cannot release a reservation.
- OpenAI sends `reasoning_effort="none"`, `temperature=0` and `max_completion_tokens`
  (which covers all billable output). Anthropic sends `temperature=0` through `extra_body`;
  Haiku 5.5 instead gets thinking disabled, because it rejects non-default sampling values.
- Both providers receive identical system and user text.

## Adding a model

1. Add a price row to `PRICING` in `llm_evals/pricing.py` from the provider's current
   pricing page, with the date you checked it.
2. Add `(provider, model)` to `GUARDED_MODELS` only after checking that the reservation
   bound holds for it: tokenizer, framing, context-size pricing tiers, reasoning tokens
   counted against the output cap, cache billing and retry behaviour. A price row alone does
   not allow paid calls.
3. Add a wire test in `tests/test_budget_and_runner.py` against the real SDK with an
   in-memory transport.

Cost is `(input - cache read - cache write) x input rate + cache read x read rate +
cache write x write rate + output x output rate`.

## Comparing results

Compare the two tasks separately. Every attempted request is in the strict-success
denominator and keeps its cost. Repetition spreads describe variation; overlapping spreads
are not an equivalence test. Do not edit gold labels, fixture texts or prompts to improve a
model's score: if a task rule changes, freeze the new version and rerun every model.
