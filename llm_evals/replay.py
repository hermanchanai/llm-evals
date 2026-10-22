"""Re-score recorded model outputs offline. No API calls, no budget, no cost.

    python -m llm_evals.replay results/recorded/2026-09-18_luna-vs-haiku.jsonl
    python -m llm_evals.replay results/recorded/*.jsonl --out results/report.md

Each recorded row carries the model's raw reply text and the token usage the provider
returned. Replay feeds the raw text through the same parser and scorer a live run uses,
and recomputes cost from the recorded usage and the price table, so a published table
can be regenerated from evidence rather than retyped.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from llm_evals import pricing, providers, run
from llm_evals.tasks import TASK_NAMES, load_cases


def load_recording(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def score_rows(rows: list[dict]):
    """Return (agg, records) in the same shape run.execute() builds."""
    cases = {task: {c["id"]: c for c in load_cases(task)[1]} for task in TASK_NAMES}
    agg = defaultdict(lambda: defaultdict(list))
    for row in rows:
        task, case = row["task"], cases[row["task"]][str(row["case"])]
        response = providers.Completion(
            text=row["raw_text"], input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"], cache_read_tokens=row["cache_read_tokens"],
            cache_write_tokens=row["cache_write_tokens"], latency_ms=row["latency_ms"],
            finish_reason=row["finish_reason"], refusal=row["refusal"])
        model = row["model"].split(":", 1)[1]
        rec = dict(task=task, model=row["model"], repetition=row["repetition"], case=case["id"],
                   attempted=True, operational_success=False, strict=False, correct=False,
                   n_pass=0, hallucinations=0, misses=0,
                   latency_ms=row["latency_ms"], raw_text=row["raw_text"],
                   cost_usd=pricing.cost_usd(model, row["input_tokens"], row["output_tokens"],
                                             row["cache_read_tokens"], row["cache_write_tokens"]),
                   recorded_cost_usd=row.get("recorded_cost_usd"))
        run.evaluate(task, case, response, rec)
        agg[(task, row["model"])]["cases"].append(rec)
    return agg


def _ok(rec):
    return bool(rec.get("strict", rec.get("correct"))) and not rec.get("error")


def detail_tables(agg) -> list[str]:
    lines = []
    rent = sorted((spec, v["cases"]) for (task, spec), v in agg.items() if task == "rent")
    if rent:
        specs = [s for s, _ in rent]
        lines += ["## Rent: strict passes per case, all repetitions (hallucinated / missed fields)", "",
                  "| case | " + " | ".join(specs) + " |", "|---|" + "---|" * len(specs)]
        ids = sorted({r["case"] for _, recs in rent for r in recs})
        for cid in ids:
            cells = []
            for _, recs in rent:
                mine = [r for r in recs if r["case"] == cid]
                cells.append(f"{sum(map(_ok, mine))}/{len(mine)} "
                             f"(h{sum(r.get('hallucinations', 0) for r in mine)}"
                             f"/m{sum(r.get('misses', 0) for r in mine)})")
            lines.append(f"| {cid} | " + " | ".join(cells) + " |")
        lines.append("")
    perm = sorted((spec, v["cases"]) for (task, spec), v in agg.items() if task == "permits")
    if perm:
        specs = [s for s, _ in perm]
        lines += ["## Permits: correct by gold class, all repetitions", "",
                  "| gold class | " + " | ".join(specs) + " |", "|---|" + "---|" * len(specs)]
        classes = sorted({r["expected"] for _, recs in perm for r in recs})
        for cls in classes:
            cells = []
            for _, recs in perm:
                mine = [r for r in recs if r["expected"] == cls]
                cells.append(f"{sum(map(_ok, mine))}/{len(mine)}")
            lines.append(f"| {cls} | " + " | ".join(cells) + " |")
        lines += ["", "## Permits: majority answer per case across repetitions, where any model missed", "",
                  "| row_id | gold | " + " | ".join(specs) + " |", "|---|---|" + "---|" * len(specs)]
        ids = sorted({r["case"] for _, recs in perm for r in recs}, key=int)
        for cid in ids:
            answers, gold, missed = [], None, False
            for _, recs in perm:
                mine = [r for r in recs if r["case"] == cid]
                gold = mine[0]["expected"]
                top = Counter(r["actual"] for r in mine).most_common(1)[0][0]
                missed |= top != gold
                answers.append(top if top == gold else f"**{top}**")
            if missed:
                lines.append(f"| {cid} | {gold} | " + " | ".join(answers) + " |")
        lines.append("")
    return lines


def render(paths: list[Path]) -> str:
    rows = [r for p in paths for r in load_recording(p)]
    agg = score_rows(rows)
    reps = max(r["repetition"] for r in rows) + 1
    title = " + ".join(Path(p).name for p in paths)
    body = run.render_report(f"replay of {title}", agg, reps)
    drift = [r for v in agg.values() for r in v["cases"]
             if r.get("recorded_cost_usd") is not None
             and abs(r["cost_usd"] - r["recorded_cost_usd"]) > 1e-6]
    lines = [body, "", *detail_tables(agg),
             "Costs are recomputed from the recorded token usage with llm_evals/pricing.py; "
             f"{len(drift)} of {sum(len(v['cases']) for v in agg.values())} rows differ from the "
             "cost recorded at run time by more than $0.000001."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recordings", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, help="write the report here instead of stdout")
    a = ap.parse_args(argv)
    report = render(a.recordings)
    if a.out:
        a.out.write_text(report)
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
