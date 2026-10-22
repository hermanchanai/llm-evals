"""Load the two tasks: system prompt plus one user message and gold label per case."""
from __future__ import annotations

import json
from pathlib import Path

from llm_evals import TASKS

RENT = TASKS / "rent_extraction"
PERM = TASKS / "permit_classification"
TASK_NAMES = ("rent", "permits")


def system_prompt(md: Path) -> str:
    return md.read_text().split("## SYSTEM", 1)[1].split("\n---", 1)[0].strip()


def permit_user_message(row_input: dict) -> str:
    """The production user message: these seven fields, compact JSON, county renamed."""
    i = row_input
    return json.dumps({"facility_name": i.get("facility_name"),
                       "application_name": i.get("application_name"),
                       "address": i.get("address"),
                       "city": i.get("city"),
                       "county": i.get("parsed_county"),
                       "acres_disturbed_project": i.get("acres_disturbed_project"),
                       "acres_disturbed_operations": i.get("acres_disturbed_operations")},
                      default=str)


def load_cases(task: str, limit: int = 0, cases_json: str | None = None):
    """Return (system_prompt, cases). Each case is {id, user, gold}.

    cases_json: an alternate permits file in goldens.json shape, e.g. a sweep whose
    expected_class is another model's stored label (the report is then agreement,
    not accuracy).
    """
    if task == "rent":
        ids = sorted(p.stem for p in (RENT / "fixtures").glob("*.txt"))[: limit or None]
        sysp = system_prompt(RENT / "PROMPT.md")
        return sysp, [dict(id=i,
                           user=(RENT / "fixtures" / f"{i}.txt").read_text(),
                           gold=json.loads((RENT / "gold" / f"{i}.json").read_text()))
                      for i in ids]
    if task != "permits":
        raise ValueError(f"unknown task {task!r}")
    source = Path(cases_json) if cases_json else PERM / "goldens.json"
    rows = json.loads(source.read_text())[: limit or None]
    sysp = system_prompt(PERM / "PROMPT.md")
    return sysp, [dict(id=str(r["row_id"]), gold=r, user=permit_user_message(r["input"]))
                  for r in rows]
