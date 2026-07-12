"""Render the scaling plots for the results section.

Reads experiments/logs/results.csv and writes PNGs into results/:
  - scaling.png            2x2 summary (correctness, hallucination, tools, time)
  - correctness_vs_size.png
  - hallucination_vs_size.png

Uses the non-interactive Agg backend so it runs headless on a laptop.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .metrics import LOG_FILE, load_results, valid_runs, _by_size  # noqa: E402

RESULTS_DIR = Path("results")


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

    # Standalone correctness + hallucination charts
    for col, title, fname in [
        ("correctness", "Correctness vs. graph size", "correctness_vs_size.png"),
        ("hallucination", "Hallucination rate vs. graph size", "hallucination_vs_size.png"),
    ]:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(x, by[col] * 100, marker="o", color="#c0392b" if "hall" in col else "#2e86de")
        ax.set_title(title)
        ax.set_xlabel("graph size (nodes)")
        ax.set_ylabel("%")
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        p = out_dir / fname
        fig.savefig(p, dpi=130)
        plt.close(fig)
        written.append(p)

    for p in written:
        print(f"Wrote {p}")
    return written


if __name__ == "__main__":
    make_plots()
