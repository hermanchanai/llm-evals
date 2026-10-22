"""The offline paths a reviewer runs first: mock runs, replay of recorded outputs,
fixture verification, and the shape and provenance of the golden sets."""
import io
import json
import os
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_evals import RESULTS, mock, providers, replay, run
from llm_evals import fixtures as build_fixtures
from llm_evals.tasks import PERM, RENT, load_cases

RECORDED = RESULTS / "recorded"
SEPT = RECORDED / "2026-09-18_luna-vs-haiku.jsonl"
OCT = RECORDED / "2026-10-18_permits-three-models.jsonl"


def table_row(report: str, section: str, model: str) -> list[str]:
    body = report.split(f"## {section}\n", 1)[1]
    line = next(x for x in body.splitlines() if x.startswith(f"| {model} |"))
    return [c.strip() for c in line.strip("|").split("|")]


# ----------------------------------------------------------------- mock provider
def run_main(argv, tmp_path):
    out = io.StringIO()
    with patch.object(sys, "argv", ["run", *argv]), patch.object(run, "RUNS", tmp_path), \
            patch.dict(os.environ, {}, clear=True), redirect_stdout(out):
        code = run.main()
    return code, out.getvalue()


def test_mock_run_needs_no_key_or_budget_and_scores_oracle_perfectly(tmp_path):
    with patch.object(providers, "_anthropic") as anthropic, patch.object(providers, "_openai") as openai:
        code, out = run_main(["--models", "mock:oracle,mock:fenced,mock:baseline",
                              "--repetitions", "1"], tmp_path)
    assert code == 0
    anthropic.assert_not_called()
    openai.assert_not_called()
    for model in ("mock:oracle", "mock:fenced"):
        rent = table_row(out, "rent", model)
        assert rent[1:4] == ["10", "10", "10"], rent  # attempted, valid, correct
        perm = table_row(out, "permits", model)
        assert perm[1:4] == ["65", "65", "65"], perm
    assert "synthetic" in out
    [run_dir] = tmp_path.iterdir()
    assert (run_dir / "report.md").read_text().strip() in out
    assert len((run_dir / "raw.jsonl").read_text().splitlines()) == 3 * 75


def test_mock_baseline_is_caught_by_the_scorer(tmp_path):
    code, out = run_main(["--models", "mock:baseline", "--repetitions", "1"], tmp_path)
    assert code == 0
    rent = table_row(out, "rent", "mock:baseline")
    assert int(rent[5]) > 0          # hallucinated zeros where gold availability is null
    assert rent[3] == "0"            # no rent record survives available=0
    perm = table_row(out, "permits", "mock:baseline")
    expected = sum(r["expected_class"] == "commercial"
                   for r in json.loads((PERM / "goldens.json").read_text()))
    assert perm[3] == str(expected)  # majority-class guess scores the base rate only


def test_unknown_mock_model_stops_before_any_call(tmp_path):
    with patch("sys.stderr", io.StringIO()):
        code, _ = run_main(["--models", "mock:nonexistent", "--repetitions", "1"], tmp_path)
    assert code == 2
    assert not list(tmp_path.iterdir())


def test_mock_answers_unknown_input_with_abstention():
    assert mock.complete("oracle", "sys", "a case that is not in the task files", 10).text == "unknown"


def test_dry_run_makes_no_calls():
    out = io.StringIO()
    argv = ["run", "--dry-run", "--models", "openai:gpt-5.6-luna,anthropic:claude-haiku-4-5"]
    with patch.object(sys, "argv", argv), patch.object(providers, "complete") as api, redirect_stdout(out):
        assert run.main() == 0
    api.assert_not_called()
    assert "rent: 10 cases x 3 repetitions = 30 calls" in out.getvalue()
    assert "permits: 65 cases x 3 repetitions = 195 calls" in out.getvalue()


# ------------------------------------------------------------- recorded outputs
@pytest.mark.parametrize("recording", [SEPT, OCT], ids=["2026-09-18", "2026-10-18"])
def test_replay_regenerates_the_committed_report(recording):
    committed = RESULTS / recording.name.replace(".jsonl", ".md")
    assert replay.render([recording]) == committed.read_text()


def test_replay_reproduces_the_published_2026_09_18_numbers():
    report = replay.render([SEPT])
    haiku = table_row(report, "rent", "anthropic:claude-haiku-4-5")
    luna = table_row(report, "rent", "openai:gpt-5.6-luna")
    # model, attempted, valid, correct, field accuracy, hallucinations, misses, strict, known $
    assert haiku[1:9] == ["30", "30", "18", "95.1%", "15", "3", "60.0%", "$0.0911"]
    assert luna[1:9] == ["30", "30", "18", "94.4%", "9", "16", "60.0%", "$0.0087"]
    haiku = table_row(report, "permits", "anthropic:claude-haiku-4-5")
    luna = table_row(report, "permits", "openai:gpt-5.6-luna")
    assert haiku[3] == "166" and haiku[8] == "$0.1335"
    assert luna[3] == "159" and luna[8] == "$0.0236"


def test_replay_reproduces_the_2026_10_18_permit_numbers():
    report = replay.render([OCT])
    correct = {m: table_row(report, "permits", m)[3] for m in
               ("anthropic:claude-haiku-4-5", "anthropic:claude-haiku-5-5", "openai:gpt-6-luna")}
    assert correct == {"anthropic:claude-haiku-4-5": "162", "anthropic:claude-haiku-5-5": "150",
                       "openai:gpt-6-luna": "160"}


@pytest.mark.parametrize("recording", [SEPT, OCT], ids=["2026-09-18", "2026-10-18"])
def test_recomputed_cost_matches_cost_recorded_at_run_time(recording):
    agg = replay.score_rows(replay.load_recording(recording))
    rows = [r for v in agg.values() for r in v["cases"]]
    assert rows and all(abs(r["cost_usd"] - r["recorded_cost_usd"]) <= 1e-6 for r in rows)


def test_recordings_carry_no_request_or_account_identifiers():
    for path in (SEPT, OCT):
        for row in replay.load_recording(path):
            assert set(row) == {"run", "task", "model", "repetition", "case", "raw_text",
                                "input_tokens", "output_tokens", "cache_read_tokens",
                                "cache_write_tokens", "latency_ms", "finish_reason", "refusal",
                                "recorded_cost_usd"}


def test_recordings_cover_every_case_and_repetition():
    rows = replay.load_recording(SEPT)
    for task, n in (("rent", 10), ("permits", 65)):
        for model in ("anthropic:claude-haiku-4-5", "openai:gpt-5.6-luna"):
            keys = {(r["case"], r["repetition"]) for r in rows if r["task"] == task and r["model"] == model}
            assert len(keys) == n * 3


# ------------------------------------------------------------------ golden sets
def test_saved_fixtures_roll_up_to_gold():
    with redirect_stdout(io.StringIO()), patch.object(sys, "argv", ["fixtures", "--verify"]):
        assert build_fixtures.main() == 0


def test_permit_goldens_shape_and_label_provenance():
    rows = json.loads((PERM / "goldens.json").read_text())
    assert len(rows) == 65 and len({r["row_id"] for r in rows}) == 65
    for r in rows:
        assert set(r) - {"input_redacted"} == {"id", "row_id", "input", "expected_class",
                                               "stratum", "label_note", "labeled_by",
                                               "label_method"}
        # Only the seven fields the production classifier sends; no person-name or
        # email-domain columns.
        assert set(r["input"]) == {"facility_name", "application_name", "address", "city",
                                   "parsed_county", "acres_disturbed_project",
                                   "acres_disturbed_operations"}
        assert r["labeled_by"] == "claude_xref_websearch"
        assert r["label_method"] == "llm_web_research"
        assert r["expected_class"] in {"single_family", "townhome", "multifamily", "mixed",
                                       "commercial", "unknown"}
    # The three private surnames are redacted, and only those.
    redacted = [r for r in rows if r.get("input_redacted")]
    assert len(redacted) == 3
    assert all("[surname]" in r["input"]["facility_name"] for r in redacted)


def test_rent_gold_shape_and_label_provenance():
    for path in sorted((RENT / "gold").glob("*.json")):
        gold = json.loads(path.read_text())
        assert set(gold) == {"fixture_id", "community_name", "units", "concession_weeks",
                             "raw_concession_text", "label_method", "labeling_notes"}
        assert gold["fixture_id"] == path.stem
        assert gold["label_method"] == "human_live_site_read"


def test_no_email_addresses_in_task_files():
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    for path in Path(RENT).rglob("*"):
        if path.is_file():
            assert not email.search(path.read_text()), path
    assert not email.search((PERM / "goldens.json").read_text())


def test_case_counts():
    assert len(load_cases("rent")[1]) == 10
    assert len(load_cases("permits")[1]) == 65
