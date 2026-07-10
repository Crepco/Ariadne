"""
Logger for Ariadne experiments.

Each run of the agent is written to a CSV file so
that metrics can later be computed.
"""

from __future__ import annotations

import csv
from pathlib import Path

# experiments/logs/results.csv
LOG_DIR = Path("experiments/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "results.csv"


FIELDS = [
    "model",
    "scenario",
    "graph_size",
    "start_node",
    "goal",
    "proposed_path",
    "tool_calls",
    "time_seconds",
    "path_valid",
    "matches_baseline",
    "hallucinated_edge",
]


def log_run(
    model: str,
    scenario: str,
    graph_size: int,
    start_node: str,
    goal: str,
    proposed_path: str,
    tool_calls: int,
    time_seconds: float,
    path_valid: bool,
    matches_baseline: bool,
    hallucinated_edge: bool,
):
    """
    Save one experiment to CSV.
    """

    file_exists = LOG_FILE.exists()

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:

        writer = csv.DictWriter(f, fieldnames=FIELDS)

        if not file_exists:
            writer.writeheader()

        writer.writerow(
            {
                "model": model,
                "scenario": scenario,
                "graph_size": graph_size,
                "start_node": start_node,
                "goal": goal,
                "proposed_path": proposed_path,
                "tool_calls": tool_calls,
                "time_seconds": round(time_seconds, 3),
                "path_valid": path_valid,
                "matches_baseline": matches_baseline,
                "hallucinated_edge": hallucinated_edge,
            }
        )

    print(f"Run saved to {LOG_FILE}")