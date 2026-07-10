"""
Compute aggregate metrics from experiment logs.
"""

from pathlib import Path
import pandas as pd


LOG_FILE = Path("experiments/logs/results.csv")


def compute_metrics():
    if not LOG_FILE.exists():
        print("No experiment log found.")
        return

    df = pd.read_csv(LOG_FILE)

    total = len(df)

    print("=" * 40)
    print("ARIADNE EXPERIMENT METRICS")
    print("=" * 40)

    print(f"Total Runs           : {total}")

    print(
        f"Path Correctness     : {(df['path_valid'].mean()*100):.2f}%"
    )

    print(
        f"Hallucination Rate   : {(df['hallucinated_edge'].mean()*100):.2f}%"
    )

    print(
        f"Avg Tool Calls       : {df['tool_calls'].mean():.2f}"
    )

    print(
        f"Avg Runtime (sec)    : {df['time_seconds'].mean():.2f}"
    )

    print("=" * 40)