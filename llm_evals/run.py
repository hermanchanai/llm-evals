"""Comparison runner. Paid calls require an initialized daily budget; mock runs do not.

    python -m llm_evals.run --dry-run --models openai:gpt-5.6-luna,anthropic:claude-haiku-4-5
    python -m llm_evals.run --models mock:oracle,mock:baseline --repetitions 1
    python -m llm_evals.run --models anthropic:claude-haiku-4-5 --daily-limit-usd 2

Dry-run token estimates are planning estimates, never spend reservations.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import tempfile
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from llm_evals import ROOT, RUNS, budget, pricing, providers, score
from llm_evals.tasks import load_cases

RENT_MAX_TOKENS, PERM_MAX_TOKENS = 4096, 10
MOCK_CEILING_USD = "1000"  # synthetic ledger for mock-only runs


def load_env():
    """Load .env for API keys if python-dotenv is installed; never required offline."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env", override=False)


def parse_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("non-finite JSON number")
    # Same two fence regexes as the production extractor: a single wrapping ``` / ```json
    # is tolerated; prose around the object is not.
    text = re.sub(r"^```(?:json)?\s*", "", (text or "").strip())
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text.strip(), object_pairs_hook=unique, parse_constant=nonfinite), ""
    except (ValueError, TypeError):
        return None, "invalid JSON (bare JSON object required; a single code fence is tolerated)"


def dry_run(tasks, models, repetitions, limit, cases_json=None):
    print("DRY RUN — no API calls.\n")
    grand = {}
    for task in tasks:
        sysp, cases = load_cases(task, limit, cases_json if task == "permits" else None)
        chars = len(sysp) * len(cases) + sum(len(c["user"]) for c in cases)
        in_tok = chars // 4                                   # ~4 chars/token
        out_tok = (300 if task == "rent" else 5) * len(cases)
        print(f"{task}: {len(cases)} cases x {repetitions} repetitions "
              f"= {len(cases)*repetitions} calls, ~{in_tok*repetitions:,} input tok "
              f"(~{out_tok*repetitions:,} output tok)")
        for spec in models:
            _, model = spec.split(":", 1)
            try:
                c = pricing.cost_usd(model, in_tok * repetitions, out_tok * repetitions)
                grand[spec] = grand.get(spec, 0.0) + c
                print(f"    {spec:<45} ~${c:0.4f}")
            except pricing.UnknownPricing as e:
                print(f"    {spec:<45} NO PRICE ROW — {e.args[0].splitlines()[0]}")
    if grand:
        print("\nestimated total per model (all selected tasks, all repetitions):")
        for k, v in sorted(grand.items(), key=lambda kv: -kv[1]):
            print(f"    {k:<45} ~${v:0.4f}")
        print(f"\n    ALL MODELS COMBINED                           ~${sum(grand.values()):0.4f}")
    print("\nToken counts are a chars/4 approximation; real usage comes back with each call.")


def evaluate(task, case, response, rec):
    """Scoring is downstream of accounting; malformed paid output still costs money."""
    error = ""
    if response.refusal:
        error = "provider refusal"
    elif response.finish_reason not in {"stop", "end_turn"}:
        error = f"incomplete output: {response.finish_reason}"
    if task == "rent":
        pred, parse_error = parse_json(response.text)
        cs = score.score_rent(case["id"], case["gold"], pred, error or parse_error)
        rec.update(n_pass=cs.n_pass, n_total=cs.n_total, strict=cs.strict,
                   operational_success=not bool(cs.parse_error),
                   hallucinations=cs.n_hallucination, misses=cs.n_miss,
                   bed_recall=[cs.bed_recall_hit, cs.bed_recall_tot],
                   bed_precision=[cs.bed_precision_hit, cs.bed_precision_tot],
                   parse_error=cs.parse_error,
                   fails=[f"{d.scope} {d.field}: gold={d.expected!r} got={d.actual!r} [{d.severity}]"
                          for d in cs.diffs if not d.passed])
        error = cs.parse_error
    else:
        got = score.normalize_class(response.text)
        error = error or ("invalid permit enum" if got == "invalid_output" else "")
        exp = case["gold"]["expected_class"]
        rec.update(expected=exp, actual=got, correct=not error and got == exp,
                   strict=not error and got == exp, operational_success=not bool(error),
                   stratum=case["gold"].get("stratum"), meta=case["gold"].get("meta"))
    if error:
        rec["error"] = error


def attempt(task, case, provider, model, system, max_tokens, ledger):
    """Reserve before dispatch; any untrusted charge stops the run with its hold intact."""
    rec = dict(attempted=False, operational_success=False, strict=False, correct=False,
               n_pass=0, n_total=(len(case["gold"]["units"])*len(score.GRADED)+1 if task == "rent" else 1),
               hallucinations=0, misses=0, cost_usd=None)
    reserve, input_bound = pricing.reservation(provider, model, system, case["user"], max_tokens)
    rid = ledger.reserve(reserve, f"{provider}:{model}", input_bound, max_tokens)
    rec.update(reservation_id=rid, reserved_usd=reserve/1_000_000, attempted=True)
    try:
        response = providers.complete(provider, model, system, case["user"], max_tokens)
    except Exception as exc:
        # Provider exception strings may contain request payloads or credentials.
        rec.update(error=f"provider request failed ({type(exc).__name__}); reservation retained", halt=True)
        return rec
    rec.update(input_tokens=response.input_tokens, output_tokens=response.output_tokens,
               cache_read_tokens=response.cache_read_tokens, cache_write_tokens=response.cache_write_tokens,
               latency_ms=response.latency_ms, raw_text=response.text,
               finish_reason=response.finish_reason, refusal=response.refusal, response_id=response.response_id)
    try:
        actual = pricing.cost_decimal(model, response.input_tokens, response.output_tokens,
                                      response.cache_read_tokens, response.cache_write_tokens)
        ledger.settle(rid, pricing.to_microusd(actual), response.input_tokens, response.output_tokens)
        rec["cost_usd"] = float(actual)
    except (pricing.UnknownUsage, pricing.UnknownPricing, budget.BudgetError):
        rec.update(error="usage/accounting untrusted; reservation retained; run stopped", halt=True)
        return rec
    try:
        evaluate(task, case, response, rec)
    except Exception as exc:
        rec.update(error=f"scoring failed ({type(exc).__name__})", operational_success=False, strict=False)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", choices=["rent", "permits", "both"], default="both")
    ap.add_argument("--models", required=True, help="comma-separated provider:model")
    ap.add_argument("--repetitions", "--seeds", dest="repetitions", type=int, default=3,
                    help="repeated requests, not supplied RNG seeds (--seeds is a legacy alias)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--daily-limit-usd", help="explicit ceiling; must match initialized shared ledger")
    ap.add_argument("--cases-json", help="permits only: alternate cases file (goldens.json shape); expected_class may be another model's label, making the report an agreement report")
    a = ap.parse_args()
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    if not models or any(m.count(":") != 1 or not all(m.split(":")) for m in models):
        ap.error("models must be provider:model pairs")
    if len(set(models)) != len(models) or a.repetitions < 1 or a.limit < 0:
        ap.error("models must be unique, repetitions positive and limit nonnegative")
    tasks = ["rent", "permits"] if a.task == "both" else [a.task]
    if a.dry_run:
        dry_run(tasks, models, a.repetitions, a.limit, a.cases_json)
        return 0
    mock_only = all(spec.split(":", 1)[0] == "mock" for spec in models)
    if not mock_only:
        load_env()
        if a.daily_limit_usd is None:
            ap.error("paid calls require --daily-limit-usd and an explicitly initialized shared ledger")
    with tempfile.TemporaryDirectory() as scratch:
        if mock_only:
            # Mock calls cost nothing; a throwaway ledger still exercises reserve/settle.
            ledger = budget.Budget(f"{scratch}/ledger.json", MOCK_CEILING_USD)
            ledger.initialize()
        else:
            ledger = budget.Budget(budget.default_path(), a.daily_limit_usd)
        return execute(a, tasks, models, ledger, mock_only)


def execute(a, tasks, models, ledger, mock_only):
    try:
        ledger.check()
        for provider in sorted({spec.split(":", 1)[0] for spec in models}):
            providers.preflight(provider)
        # Check every selected request's price/bound policy before ANY dispatch.
        for task in tasks:
            sysp, cases = load_cases(task, a.limit, a.cases_json if task == "permits" else None)
            for spec in models:
                provider, model = spec.split(":", 1)
                for case in cases:
                    pricing.reservation(provider, model, sysp, case["user"],
                                        RENT_MAX_TOKENS if task == "rent" else PERM_MAX_TOKENS)
    except (budget.BudgetError, ValueError) as exc:
        print(f"Stopped before any paid call: {exc}", file=sys.stderr)
        return 2
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    outdir = RUNS / run_id
    outdir.mkdir(parents=True, exist_ok=False)
    agg = defaultdict(lambda: defaultdict(list))
    halted = False
    with (outdir / "raw.jsonl").open("x") as raw:
        for task in tasks:
            sysp, cases = load_cases(task, a.limit, a.cases_json if task == "permits" else None)
            mt = RENT_MAX_TOKENS if task == "rent" else PERM_MAX_TOKENS
            for spec in models:
                provider, model = spec.split(":", 1)
                for repetition in range(a.repetitions):
                    for case in cases:
                        rec = dict(task=task, model=spec, repetition=repetition, case=case["id"])
                        try:
                            rec.update(attempt(task, case, provider, model, sysp, mt, ledger))
                        except (budget.BudgetError, pricing.UnknownUsage, pricing.UnknownPricing) as exc:
                            rec.update(attempted=False, error=str(exc), halt=True)
                        agg[(task, spec)]["cases"].append(rec)
                        raw.write(json.dumps(rec, allow_nan=False) + "\n")
                        raw.flush()
                        if rec.get("halt"):
                            halted = True
                            break
                    print(f"  {task} {spec} repetition {repetition + 1} {'stopped' if halted else 'done'}", flush=True)
                    if halted:
                        break
                if halted:
                    break
            if halted:
                break
    report = render_report(run_id, agg, a.repetitions)
    if mock_only:
        report += "\n\nMock provider: token counts and costs are synthetic, not measurements."
    if halted:
        report += "\n\nRUN STOPPED EARLY. Remaining planned requests were not attempted."
    (outdir / "report.md").write_text(report)
    print("\n" + report)
    print(f"\nResults: {outdir}")
    return 2 if halted else 0


def render_report(run_id, agg, repetitions):
    lines = [f"# Evaluation: {run_id}", "", f"Planned repetitions per model: {repetitions} (no RNG seed supplied)", ""]
    for task in ("rent", "permits"):
        rows = [(key[1], value["cases"]) for key, value in agg.items() if key[0] == task]
        if not rows:
            continue
        lines += [f"## {task}", "",
                  "| model | attempted | valid complete | correct records | field accuracy | hallucinations | misses | strict / attempted | known $ total | unknown costs | $/1k attempted | $/1k correct | p50 ms | p95 ms | repetition strict spread |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for spec, records in sorted(rows):
            cases = [c for c in records if c.get("attempted", True)]
            n = len(cases)
            correct = sum(bool(c.get("strict", c.get("correct", False))) and not c.get("error") for c in cases)
            valid = sum(c.get("operational_success", "error" not in c) for c in cases)
            if task == "rent":
                fields = sum(c.get("n_total", 0) for c in cases)
                accuracy = sum(c.get("n_pass", 0) for c in cases)/fields if fields else 0
            else:
                accuracy = correct/n if n else 0
            strict = correct/n if n else 0
            known = [c["cost_usd"] for c in cases if c.get("cost_usd") is not None]
            unknown = n-len(known)
            total = sum(known)
            cost_total = f"${total:.4f}" + (" (partial)" if unknown else "")
            per_call = f"${total/n*1000:.4f}" if n and not unknown else "-"
            per_correct = f"${total/correct*1000:.4f}" if correct and not unknown else "-"
            latencies = sorted(c["latency_ms"] for c in cases if "latency_ms" in c)
            p50 = str(latencies[len(latencies)//2]) if latencies else "-"
            p95 = str(latencies[math.ceil(len(latencies)*.95)-1]) if latencies else "-"
            spread = []
            for rep in range(repetitions):
                group = [c for c in cases if c.get("repetition", c.get("seed")) == rep]
                if group:
                    spread.append(sum(bool(c.get("strict", c.get("correct", False))) and not c.get("error") for c in group)/len(group))
            spread_text = f"{min(spread):.1%}-{max(spread):.1%}" if len(spread) > 1 else "n/a"
            hal = sum(c.get("hallucinations", 0) for c in cases)
            misses = sum(c.get("misses", 0) for c in cases)
            lines.append(f"| {spec} | {n} | {valid} | {correct} | {accuracy:.1%} | {hal} | {misses} | {strict:.1%} | {cost_total} | {unknown} | {per_call} | {per_correct} | {p50} | {p95} | {spread_text} |")
        lines += ["", "### Errors and disagreements (first repetition)", ""]
        for spec, records in sorted(rows):
            for rec in records:
                if rec.get("repetition", rec.get("seed", 0)) != 0:
                    continue
                detail = rec.get("error") or "; ".join(rec.get("fails", []))
                if task == "permits" and not detail and not rec.get("correct", False):
                    detail = f"{rec.get('expected')} -> {rec.get('actual')}"
                if detail:
                    lines.append(f"- **{spec}** `{rec.get('case', '?')}`: {detail}")
        lines.append("")
    lines += ["All attempted calls enter strict success, including API, parse, schema, refusal and truncation failures.",
              "Known costs include failed outputs. Unknown charges remain reserved; cost rankings are withheld when any cost is unknown.",
              "Hallucinations are incorrect fields and also shown separately. Rent field accuracy weights fields; strict success weights records.",
              "Repetition ranges are descriptive; overlapping ranges do not prove model equivalence."]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
