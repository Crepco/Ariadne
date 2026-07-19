"""Render the scaling plots for the results section.

Reads experiments/logs/results.csv and writes PNGs into results/:
  - scaling.png            2x2 summary (correctness, hallucination, tools, time)
  - correctness_vs_size.png    with bootstrap 95% CI error bars
  - hallucination_vs_size.png
  - failure_modes.png      stacked outcome-bucket proportions by graph size

Uses the non-interactive Agg backend so it runs headless on a laptop.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .metrics import (  # noqa: E402
    _MODE_LABELS,
    _MODES,
    _by_size,
    _failure_modes,
    LOG_FILE,
    load_results,
    valid_runs,
)

RESULTS_DIR = Path("results")


def _bootstrap_ci(values: np.ndarray, n: int = 2000, alpha: float = 0.05, seed: int = 1337):
    """Percentile bootstrap CI (in %) for the mean of a 0/1 array."""
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n, values.size), replace=True).mean(axis=1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return values.mean() * 100, lo * 100, hi * 100


def make_plots(path: Path = LOG_FILE, out_dir: Path = RESULTS_DIR) -> list[Path]:
    raw = load_results(path)
    if raw is None or raw.empty:
        print("No results to plot.")
        return []
    df = valid_runs(raw)
    if df.empty:
        print("No successful runs to plot.")
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    by = _by_size(df)
    x = by["graph_size"]
    written: list[Path] = []

    panels = [
        ("correctness", "Correctness", lambda v: v * 100, "%", (0, 100)),
        ("hallucination", "Hallucination rate", lambda v: v * 100, "%", (0, 100)),
        ("avg_tool_calls", "Avg tool calls", lambda v: v, "calls", None),
        ("avg_time", "Avg time", lambda v: v, "seconds", None),
    ]

    # Combined 2x2 summary
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for ax, (col, title, fn, unit, ylim) in zip(axes.flat, panels):
        ax.plot(x, by[col].map(fn), marker="o")
        ax.set_title(title)
        ax.set_xlabel("graph size (nodes)")
        ax.set_ylabel(unit)
        if ylim:
            ax.set_ylim(*ylim)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Ariadne — agent behaviour vs. graph size")
    fig.tight_layout()
    summary = out_dir / "scaling.png"
    fig.savefig(summary, dpi=130)
    plt.close(fig)
    written.append(summary)

    # Correctness with bootstrap 95% CI error bars
    sizes = sorted(df["graph_size"].dropna().unique())
    means, los, his = [], [], []
    for s in sizes:
        m, lo, hi = _bootstrap_ci(df[df["graph_size"] == s]["correct"].to_numpy())
        means.append(m)
        los.append(m - lo)
        his.append(hi - m)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.errorbar(sizes, means, yerr=[los, his], marker="o", color="#2e86de", capsize=4)
    ax.set_title("Correctness vs. graph size (95% CI)")
    ax.set_xlabel("graph size (nodes)")
    ax.set_ylabel("%")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    p = out_dir / "correctness_vs_size.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    written.append(p)

    # Standalone hallucination chart
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, by["hallucination"] * 100, marker="o", color="#c0392b")
    ax.set_title("Hallucination rate vs. graph size")
    ax.set_xlabel("graph size (nodes)")
    ax.set_ylabel("%")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    p = out_dir / "hallucination_vs_size.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    written.append(p)

    # Failure-mode stacked bar (proportions) by graph size
    fm = _failure_modes(df)
    totals = fm.sum(axis=1).replace(0, 1)
    props = fm.div(totals, axis=0)
    colors = {
        "correct": "#27ae60",
        "hallucinated": "#c0392b",
        "false_no_path": "#e67e22",
        "incomplete": "#7f8c8d",
        "wrong_path": "#8e44ad",
    }
    fig, ax = plt.subplots(figsize=(7, 4))
    bottom = np.zeros(len(props))
    xs = [str(int(s)) for s in props.index]
    for m in _MODES:
        ax.bar(xs, props[m].to_numpy() * 100, bottom=bottom, label=_MODE_LABELS[m], color=colors[m])
        bottom += props[m].to_numpy() * 100
    ax.set_title("Outcome breakdown vs. graph size")
    ax.set_xlabel("graph size (nodes)")
    ax.set_ylabel("% of runs")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8, loc="lower center", bbox_to_anchor=(0.5, -0.35), ncol=3)
    fig.tight_layout()
    p = out_dir / "failure_modes.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    written.append(p)

    for p in written:
        print(f"Wrote {p}")
    return written


if __name__ == "__main__":
    make_plots()
