"""Aggregate metrics from experiment logs — the project's results table.

Reads experiments/logs/results.csv and reports the plan's Part-7 metrics:
path-correctness, hallucination rate, time-to-solution, tool-call efficiency,
scaling behaviour (broken out by graph size), and the gap vs. the BloodHound
baseline. ``compute_metrics`` prints them; ``metrics_markdown`` returns the same
tables as Markdown for the paper.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

LOG_FILE = Path("experiments/logs/results.csv")

_BOOL_COLS = [
    "path_valid", "hallucinated_edge", "correct", "declared_no_path", "incomplete",
    "baseline_reachable", "matches_baseline", "optimal",
]
_NUM_COLS = ["graph_size", "agent_hops", "baseline_hops", "tool_calls", "steps", "time_seconds"]


def load_results(path: Path = LOG_FILE) -> pd.DataFrame | None:
    """Load the log and coerce CSV strings back into bools / numbers."""
    if not path.exists():
        return None
    df = pd.read_csv(path)
    for c in _BOOL_COLS:
        if c in df:
            df[c] = df[c].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    for c in _NUM_COLS:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def valid_runs(df: pd.DataFrame) -> pd.DataFrame:
    """Drop runs that failed for infrastructure reasons (e.g. LLM unreachable).

    Those must never be counted as hallucinations or misses — they aren't the
    agent being wrong, they're the run not happening. Note: an empty CSV field
    reads back as NaN, and pandas 3.x keeps NaN through ``astype(str)``, so we
    test for missing values with ``isna()`` rather than string comparison.
    """
    if "error" not in df:
        return df
    s = df["error"].astype(str).str.strip().str.lower()
    is_blank = df["error"].isna() | s.isin(["", "nan", "none"])
    return df[is_blank]


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _overall(df: pd.DataFrame) -> dict:
    total = len(df)
    solved = df[df["correct"]]
    reachable = df[df["baseline_reachable"]]
    agent_miss = df[df["baseline_reachable"] & ~df["correct"]]
    return {
        "runs": total,
        "correctness": df["correct"].mean() if total else 0.0,
        "path_valid": df["path_valid"].mean() if total else 0.0,
        "hallucination": df["hallucinated_edge"].mean() if total else 0.0,
        "incomplete": int(df["incomplete"].sum()) if "incomplete" in df else 0,
        "avg_tool_calls_correct": solved["tool_calls"].mean() if len(solved) else float("nan"),
        "avg_time": df["time_seconds"].mean() if total else float("nan"),
        "optimal_of_solved": (df["optimal"].sum() / len(solved)) if len(solved) else float("nan"),
        "reachable": len(reachable),
        "agent_miss": len(agent_miss),
    }


def _by_size(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("graph_size")
    out = g.agg(
        runs=("correct", "size"),
        correctness=("correct", "mean"),
        hallucination=("hallucinated_edge", "mean"),
        avg_tool_calls=("tool_calls", "mean"),
        avg_time=("time_seconds", "mean"),
    ).reset_index()
    return out.sort_values("graph_size")


def compute_metrics(path: Path = LOG_FILE) -> pd.DataFrame | None:
    raw = load_results(path)
    if raw is None or raw.empty:
        print("No experiment log found (run the benchmark or run.py first).")
        return None

    df = valid_runs(raw)
    excluded = len(raw) - len(df)
    if df.empty:
        print(f"All {len(raw)} runs failed for infrastructure reasons — no metrics to report.")
        return None

    o = _overall(df)
    print("=" * 52)
    print("ARIADNE — RESULTS")
    print("=" * 52)
    if excluded:
        print(f"(excluded {excluded} run(s) with infrastructure errors)")
    print(f"Total runs             : {o['runs']}")
    print(f"Correctness            : {_pct(o['correctness'])}  "
          f"(right answer; incl. correctly declaring NO PATH)")
    print(f"Valid-path rate        : {_pct(o['path_valid'])}")
    print(f"Hallucination rate     : {_pct(o['hallucination'])}")
    print(f"Incomplete (no answer) : {o['incomplete']}")
    print(f"Avg tool calls (solved): {o['avg_tool_calls_correct']:.2f}")
    print(f"Avg runtime (s)        : {o['avg_time']:.2f}")
    if o["reachable"]:
        print(f"Optimal-length (solved): {_pct(o['optimal_of_solved'])}")
    print(f"Gap vs BloodHound      : {o['agent_miss']}/{o['reachable']} reachable cases the agent missed")

    print("\nScaling by graph size:")
    by = _by_size(df)
    print(f"  {'nodes':>6}  {'runs':>4}  {'correct':>8}  {'halluc':>7}  {'tools':>6}  {'time(s)':>7}")
    for _, r in by.iterrows():
        print(f"  {int(r['graph_size']):>6}  {int(r['runs']):>4}  "
              f"{_pct(r['correctness']):>8}  {_pct(r['hallucination']):>7}  "
              f"{r['avg_tool_calls']:>6.1f}  {r['avg_time']:>7.2f}")
    print("=" * 52)
    return df


def metrics_markdown(path: Path = LOG_FILE) -> str:
    """Return the results as Markdown tables (for paper/paper.md)."""
    raw = load_results(path)
    if raw is None or raw.empty:
        return "_No results logged yet._\n"

    df = valid_runs(raw)
    if df.empty:
        return "_All logged runs failed for infrastructure reasons._\n"

    o = _overall(df)
    lines = [
        "### Overall",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Runs | {o['runs']} |",
        f"| Correctness | {_pct(o['correctness'])} |",
        f"| Valid-path rate | {_pct(o['path_valid'])} |",
        f"| Hallucination rate | {_pct(o['hallucination'])} |",
        f"| Avg tool calls (solved) | {o['avg_tool_calls_correct']:.2f} |",
        f"| Avg runtime (s) | {o['avg_time']:.2f} |",
        f"| Agent misses (of reachable) | {o['agent_miss']}/{o['reachable']} |",
        "",
        "### Scaling by graph size",
        "",
        "| Nodes | Runs | Correctness | Hallucination | Avg tool calls | Avg time (s) |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, r in _by_size(df).iterrows():
        lines.append(
            f"| {int(r['graph_size'])} | {int(r['runs'])} | {_pct(r['correctness'])} | "
            f"{_pct(r['hallucination'])} | {r['avg_tool_calls']:.1f} | {r['avg_time']:.2f} |"
        )
    return "\n".join(lines) + "\n"
