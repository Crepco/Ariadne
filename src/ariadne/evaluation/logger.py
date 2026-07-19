"""Logger for Ariadne experiments.

One CSV row per agent run. ``log_row`` is the primary API (takes a dict);
``log_run`` is kept as a keyword-argument wrapper for older call sites.
"""

from __future__ import annotations

import csv
from pathlib import Path

LOG_DIR = Path("experiments/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "results.csv"

FIELDS = [
    "model",
    "graph_size",
    "scenario",
    "start_name",
    "start_node",
    "goal",
    "proposed_path",
    "path_valid",
    "hallucinated_edge",
    "correct",
    "declared_no_path",
    "incomplete",
    "agent_hops",
    "derived_steps",          # inferred (non-edge) hops the agent's path used
    "baseline_reachable",     # TRUE reachability (canonical edges + inference)
    "baseline_hops",
    "bloodhound_reachable",   # canonical-only reachability (rule-based baseline)
    "bloodhound_hops",
    "beats_bloodhound",       # agent found a real path BloodHound's query misses
    "matches_baseline",
    "optimal",
    "tool_calls",
    "steps",
    "max_steps",
    "time_seconds",
    "prompt_tokens",
    "completion_tokens",
    "cost_usd",
    "error",
]


def reset_log(path: Path = LOG_FILE) -> None:
    """Start a fresh results file (used at the top of a benchmark sweep)."""
    if path.exists():
        path.unlink()


def log_row(row: dict, path: Path = LOG_FILE) -> None:
    """Append one run to the CSV, filling any missing columns with ''."""
    if "time_seconds" in row and isinstance(row["time_seconds"], (int, float)):
        row = {**row, "time_seconds": round(row["time_seconds"], 3)}

    file_exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in FIELDS})
    print(f"Run saved to {path}")


def log_run(**kwargs) -> None:
    """Backward-compatible wrapper: accepts the old keyword arguments."""
    log_row(kwargs)
