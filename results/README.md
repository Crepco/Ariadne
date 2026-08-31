# results/

Generated outputs from the real-data benchmark — the numbers and figures that go into the
paper. Everything here is produced by
[`experiments/run_real.py`](../experiments/run_real.py) (via `src/ariadne/evaluation/`)
against a real, ingested BloodHound/SharpHound export; re-run it to refresh.

| File | Contents |
| --- | --- |
| `metrics.md` | Overall + per-model results table (Markdown), rates with 95% Wilson intervals |
| `model_comparison.png` | Correctness vs. hallucination, per model — the paper's primary figure |
| `failure_modes.png` | Outcome breakdown: correct / hallucinated / gave up / ran out of steps / wrong path |
| `scaling.png`, `correctness_vs_size.png`, `hallucination_vs_size.png` | Legacy per-graph-size plots from `experiments/run_benchmark.py`'s synthetic sweeps; not meaningful for the current single-graph real-data run (one x-axis point) and not referenced in the paper — regenerate a synthetic sweep to make these informative again |
| `runs/` | **Archived raw CSVs**, one per sweep, each with a `.json` of its provenance |

These are committed so the repo is self-demonstrating. Don't hand-edit them — they're
regenerated from `experiments/logs/results.csv` on every benchmark run.

## `runs/` — why the raw CSVs are committed

`experiments/logs/results.csv` is the *live* log; `run_real.py` is resumable and appends to
it, skipping any `(model, start)` pair that already has a successful row, so a run
interrupted by a laptop sleep or a network drop continues rather than restarting. The
archive in `runs/` is a timestamped snapshot alongside a `.json` recording the dataset
description, model ids, start users, and step budget — the closest thing to a fixed
provenance record, since the live log keeps accumulating.

The current `metrics.md` (5 models, 26 scored runs, real GOAD-Light data) was regenerated
from the fully-resumed log after `claude-opus-4-8`'s 2-run subset was re-run against a
freshly re-ingested copy of the real graph (Neo4j had briefly held a synthetic graph from an
aborted comparison sweep in between); the raw per-run data behind every number in the paper
is `runs/20260831-075906-real-goad.csv` plus the two `claude-opus-4-8` rows added after.

## Reading the intervals

Rates carry 95% Wilson score intervals, not point estimates, because this benchmark's
samples are small (6 runs for four models, 2 for one, deliberately — see the paper's
Section 5) and its rates sit at the extremes, exactly where the normal approximation
collapses to zero width and implies a certainty the data doesn't support. A 66.7%
correctness over 6 runs is `66.7% [30.0–90.3]`; a 50.0% hallucination rate over 2 runs is
`50.0% [9.5–90.5]` (that model's own interval — the overall 3.8% figure in `metrics.md`
pools all 26 runs).
