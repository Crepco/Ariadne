"""Aggregate metrics from experiment logs — the project's results table.

Reads experiments/logs/results.csv and reports: path-correctness, hallucination
rate, time-to-solution, tool-call efficiency, token/cost usage, scaling behaviour
(broken out by graph size), a failure-mode breakdown, and — the headline — how
the agent compares to the rule-based BloodHound baseline, including cases where it
finds a real path the canonical shortest-path query misses. ``compute_metrics``
prints them; ``metrics_markdown`` returns the same tables as Markdown for the paper.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LOG_FILE = Path("experiments/logs/results.csv")

_BOOL_COLS = [
    "path_valid", "hallucinated_edge", "correct", "declared_no_path", "incomplete",
    "baseline_reachable", "bloodhound_reachable", "beats_bloodhound",
    "matches_baseline", "optimal",
]
_NUM_COLS = [
    "graph_size", "agent_hops", "baseline_hops", "bloodhound_hops", "derived_steps",
    "tool_calls", "steps", "max_steps", "time_seconds",
    "prompt_tokens", "completion_tokens", "cost_usd",
]

# Mutually-exclusive per-run outcome buckets (checked in this order).
_MODES = ["correct", "hallucinated", "false_no_path", "incomplete", "wrong_path"]
_MODE_LABELS = {
    "correct": "correct",
    "hallucinated": "hallucinated",
    "false_no_path": "gave up (path existed)",
    "incomplete": "ran out of steps",
    "wrong_path": "wrong path",
}


def load_results(path: Path = LOG_FILE) -> pd.DataFrame | None:
    """Load the log and coerce CSV strings back into bools / numbers.

    Missing columns (e.g. an older log written before a new metric existed) are
    filled with defaults so downstream aggregation never KeyErrors.
    """
    if not path.exists():
        return None
    df = pd.read_csv(path)
    for c in _BOOL_COLS:
        if c in df:
            df[c] = df[c].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
        else:
            df[c] = False
    for c in _NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df else np.nan
    if "model" not in df:                      # pre-multi-model logs
        df["model"] = "default"
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


def classify(df: pd.DataFrame) -> pd.Series:
    """Assign each run to exactly one outcome bucket (see ``_MODES``)."""
    return pd.Series(
        np.select(
            [df["correct"], df["incomplete"], df["hallucinated_edge"], df["declared_no_path"]],
            ["correct", "incomplete", "hallucinated", "false_no_path"],
            default="wrong_path",
        ),
        index=df.index,
    )


def _failure_modes(df: pd.DataFrame) -> pd.DataFrame:
    """Outcome-bucket counts per graph size (columns ordered as ``_MODES``)."""
    d = df.assign(mode=classify(df))
    tab = d.groupby(["graph_size", "mode"]).size().unstack(fill_value=0)
    for m in _MODES:
        if m not in tab:
            tab[m] = 0
    return tab[_MODES].sort_index()


def _overall(df: pd.DataFrame) -> dict:
    total = len(df)
    solved = df[df["correct"]]
    found = df[df["path_valid"]]                     # runs where a REAL path was proposed
    reachable = df[df["baseline_reachable"]]         # truly reachable (all edges)
    agent_miss = df[df["baseline_reachable"] & ~df["correct"]]
    # Cases the rule-based baseline can't reach but that ARE truly reachable —
    # i.e. escalation requires advanced (inferred) tradecraft.
    advanced_required = df[df["baseline_reachable"] & ~df["bloodhound_reachable"]]
    advanced_solved = advanced_required[advanced_required["correct"]]
    tokens = df["prompt_tokens"].fillna(0) + df["completion_tokens"].fillna(0)
    return {
        "runs": total,
        "correctness": df["correct"].mean() if total else 0.0,
        "path_valid": df["path_valid"].mean() if total else 0.0,
        "hallucination": df["hallucinated_edge"].mean() if total else 0.0,
        "incomplete": int(df["incomplete"].sum()),
        "avg_tool_calls_correct": solved["tool_calls"].mean() if len(solved) else float("nan"),
        "avg_time": df["time_seconds"].mean() if total else float("nan"),
        # Of paths actually found, how many are shortest (denominator = found, not
        # all correct — the latter also counts correct "no path" runs w/o a length).
        "found": len(found),
        "optimal_of_found": (df["optimal"].sum() / len(found)) if len(found) else float("nan"),
        "reachable": len(reachable),
        "agent_miss": len(agent_miss),
        # BloodHound comparison
        "beats_bloodhound": int(df["beats_bloodhound"].sum()),
        "advanced_required": len(advanced_required),
        "advanced_solved": len(advanced_solved),
        "advanced_recall": (len(advanced_solved) / len(advanced_required))
        if len(advanced_required) else float("nan"),
        # Cost / tokens
        "avg_tokens": tokens.mean() if total else float("nan"),
        "avg_cost": df["cost_usd"].mean() if total else float("nan"),
        "total_cost": df["cost_usd"].fillna(0).sum(),
    }


def _by_size(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("graph_size")
    out = g.agg(
        runs=("correct", "size"),
        correctness=("correct", "mean"),
        hallucination=("hallucinated_edge", "mean"),
        beats_bloodhound=("beats_bloodhound", "sum"),
        avg_tool_calls=("tool_calls", "mean"),
        avg_time=("time_seconds", "mean"),
    ).reset_index()
    return out.sort_values("graph_size")


def _by_model(df: pd.DataFrame) -> pd.DataFrame:
    """Per-model aggregates (mirrors ``_by_size``). Empty unless ≥2 models are
    present, so the breakdown only surfaces for an actual multi-model comparison."""
    if "model" not in df or df["model"].nunique() < 2:
        return pd.DataFrame()
    out = df.groupby("model").agg(
        runs=("correct", "size"),
        correctness=("correct", "mean"),
        hallucination=("hallucinated_edge", "mean"),
        beats_bloodhound=("beats_bloodhound", "sum"),
        avg_tool_calls=("tool_calls", "mean"),
        avg_time=("time_seconds", "mean"),
        avg_cost=("cost_usd", "mean"),
    ).reset_index()
    return out.sort_values("correctness", ascending=False)


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
    if o["found"]:
        print(f"Optimal of paths found : {_pct(o['optimal_of_found'])}  ({o['found']} real paths found)")
    print(f"Agent misses (truth)   : {o['agent_miss']}/{o['reachable']} truly-reachable cases missed")
    print(f"Beats BloodHound       : {o['beats_bloodhound']} run(s) found a real path the canonical "
          f"query misses  (of {o['advanced_required']} advanced-required case(s))")
    if o["advanced_required"]:
        print(f"Advanced-case recall   : {_pct(o['advanced_recall'])}  "
              f"({o['advanced_solved']}/{o['advanced_required']} inference-only cases solved)")
    if not np.isnan(o["avg_cost"]):
        print(f"Avg tokens/run         : {o['avg_tokens']:.0f}")
        print(f"Cost (USD)             : ${o['avg_cost']:.4f}/run, ${o['total_cost']:.4f} total")

    print("\nScaling by graph size:")
    by = _by_size(df)
    print(f"  {'nodes':>6}  {'runs':>4}  {'correct':>8}  {'halluc':>7}  {'beatsBH':>7}  {'tools':>6}  {'time(s)':>7}")
    for _, r in by.iterrows():
        print(f"  {int(r['graph_size']):>6}  {int(r['runs']):>4}  "
              f"{_pct(r['correctness']):>8}  {_pct(r['hallucination']):>7}  "
              f"{int(r['beats_bloodhound']):>7}  {r['avg_tool_calls']:>6.1f}  {r['avg_time']:>7.2f}")

    bm = _by_model(df)
    if not bm.empty:
        print("\nBy model:")
        print(f"  {'model':<28}  {'runs':>4}  {'correct':>8}  {'halluc':>7}  {'beatsBH':>7}  "
              f"{'tools':>6}  {'time(s)':>7}  {'$/run':>8}")
        for _, r in bm.iterrows():
            cost = f"${r['avg_cost']:.4f}" if not np.isnan(r["avg_cost"]) else "  n/a"
            print(f"  {str(r['model']):<28}  {int(r['runs']):>4}  {_pct(r['correctness']):>8}  "
                  f"{_pct(r['hallucination']):>7}  {int(r['beats_bloodhound']):>7}  "
                  f"{r['avg_tool_calls']:>6.1f}  {r['avg_time']:>7.2f}  {cost:>8}")

    print("\nFailure-mode breakdown by graph size:")
    fm = _failure_modes(df)
    header = "  " + f"{'nodes':>6}  " + "  ".join(f"{_MODE_LABELS[m]:>22}" for m in _MODES)
    print(header)
    for size, row in fm.iterrows():
        print("  " + f"{int(size):>6}  " + "  ".join(f"{int(row[m]):>22}" for m in _MODES))
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
        f"| Optimal of paths found | {_pct(o['optimal_of_found'])} ({o['found']} found) |",
        f"| Beats BloodHound | {o['beats_bloodhound']} of {o['advanced_required']} advanced-required |",
        f"| Advanced-case recall | {_pct(o['advanced_recall'])} ({o['advanced_solved']}/{o['advanced_required']}) |",
        f"| Avg tool calls (solved) | {o['avg_tool_calls_correct']:.2f} |",
        f"| Avg runtime (s) | {o['avg_time']:.2f} |",
        f"| Agent misses (of truly reachable) | {o['agent_miss']}/{o['reachable']} |",
    ]
    if not np.isnan(o["avg_cost"]):
        lines.append(f"| Cost (USD) | ${o['avg_cost']:.4f}/run, ${o['total_cost']:.4f} total |")
    lines += [
        "",
        "### Scaling by graph size",
        "",
        "| Nodes | Runs | Correctness | Hallucination | Beats BH | Avg tool calls | Avg time (s) |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, r in _by_size(df).iterrows():
        lines.append(
            f"| {int(r['graph_size'])} | {int(r['runs'])} | {_pct(r['correctness'])} | "
            f"{_pct(r['hallucination'])} | {int(r['beats_bloodhound'])} | "
            f"{r['avg_tool_calls']:.1f} | {r['avg_time']:.2f} |"
        )
    bm = _by_model(df)
    if not bm.empty:
        lines += [
            "",
            "### By model",
            "",
            "| Model | Runs | Correctness | Hallucination | Beats BH | Avg tool calls | Avg time (s) | Avg cost |",
            "| :-- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for _, r in bm.iterrows():
            cost = f"${r['avg_cost']:.4f}" if not np.isnan(r["avg_cost"]) else "n/a"
            lines.append(
                f"| {r['model']} | {int(r['runs'])} | {_pct(r['correctness'])} | "
                f"{_pct(r['hallucination'])} | {int(r['beats_bloodhound'])} | "
                f"{r['avg_tool_calls']:.1f} | {r['avg_time']:.2f} | {cost} |"
            )

    lines += [
        "",
        "### Failure-mode breakdown by graph size",
        "",
        "| Nodes | " + " | ".join(_MODE_LABELS[m] for m in _MODES) + " |",
        "| ---: | " + " | ".join("---:" for _ in _MODES) + " |",
    ]
    for size, row in _failure_modes(df).iterrows():
        lines.append(f"| {int(size)} | " + " | ".join(str(int(row[m])) for m in _MODES) + " |")
    return "\n".join(lines) + "\n"
