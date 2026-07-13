# results/

Generated outputs from the benchmark — the numbers and figures that go into the write-up.
Everything here is produced by [`experiments/run_benchmark.py`](../experiments/run_benchmark.py)
(via `src/ariadne/evaluation/`); re-run it to refresh.

| File | Contents |
| --- | --- |
| `metrics.md` | Overall + per-graph-size results table (Markdown) |
| `scaling.png` | 2×2 summary: correctness, hallucination, tool calls, and time vs. graph size |
| `correctness_vs_size.png` | Correctness vs. graph size |
| `hallucination_vs_size.png` | Hallucination rate vs. graph size |

These are committed so the repo is self-demonstrating. Don't hand-edit them — they're
regenerated from `experiments/logs/results.csv` on every benchmark run.
