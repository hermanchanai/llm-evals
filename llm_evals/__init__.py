"""Accuracy-and-cost evaluation harness for two real-estate LLM tasks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "tasks"
RESULTS = ROOT / "results"
RUNS = ROOT / "runs"  # new runs land here; gitignored
