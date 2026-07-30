# results/

Generated outputs from the benchmark — the numbers and figures that go into the write-up.
Everything here is produced by [`experiments/run_benchmark.py`](../experiments/run_benchmark.py)
(via `src/ariadne/evaluation/`); re-run it to refresh.

| File | Contents |
| --- | --- |
| `metrics.md` | Overall + per-graph-size results table (Markdown), rates with 95% Wilson intervals |
| `scaling.png` | 2×2 summary: correctness, hallucination, tool calls, and time vs. graph size |
| `correctness_vs_size.png` | Correctness vs. graph size |
| `hallucination_vs_size.png` | Hallucination rate vs. graph size |
| `model_comparison.png` | Correctness vs. hallucination, per model |
| `runs/` | **Archived raw CSVs**, one per sweep, each with a `.json` of its provenance |

These are committed so the repo is self-demonstrating. Don't hand-edit them — they're
regenerated from `experiments/logs/results.csv` on every benchmark run.

## `runs/` — why the raw CSVs are committed

`experiments/logs/results.csv` is the *live* log and is overwritten by the next sweep, so
on its own it can't back a published table. Every run of `run_benchmark.py` therefore also
archives a timestamped copy here alongside a `.json` recording the git SHA, model ids,
temperature, seed, graph sizes, step budget, and the **attempted vs. scored** counts per
model.

That last pair is the one to check before quoting a rate. Runs that fail for infrastructure
reasons (exhausted API credit, rate limits) are excluded from the metrics — correctly, since
they aren't the agent being wrong — but excluding them also selects for the runs that got
through. The provenance file makes the size of that exclusion visible instead of leaving it
in a footnote.

> **The current `metrics.md` predates this archive.** Its sweep ran before per-run CSVs were
> retained, and the live log was overwritten, so there is no `runs/` entry backing it. Its
> numbers stand as reported but are not independently checkable; the next sweep will be.

## Reading the intervals

Rates carry 95% Wilson score intervals, not point estimates, because this benchmark's
samples are small and its rates sit at the extremes — exactly where the normal
approximation collapses to zero width and implies a certainty the data doesn't support.
A 100% correctness over 11 runs is `100% [74.1–100]`; a 0% hallucination rate over 37 runs
is `0% [0–9.4]`.
