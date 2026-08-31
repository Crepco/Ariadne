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
| `runs/` | **Archived raw CSVs**, one per sweep, each with a `.json` of its provenance |

There is deliberately no per-graph-size scaling plot: this benchmark runs against one real,
live-collected graph (147 nodes), not a swept series of synthetic sizes, so a "vs. graph
size" x-axis would have exactly one point. `experiments/run_benchmark.py` (the synthetic
generator + sweep) still exists in this codebase and can produce that kind of plot again if
a future synthetic comparison is wanted, but nothing synthetic is reported in the paper or
committed under `results/`.

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
correctness over 6 runs is `66.7% [30.0–90.3]`; `claude-opus-4-8`'s 0.0% correctness over
its 2-run subset is `0.0% [0.0–65.8]` — an interval wide enough that it must not be read as
"this model never solves this task," only as "this model solved neither of the 2 cases we
could afford to run against it." The overall 3.8% [0.7–18.9] hallucination figure in
`metrics.md` pools all 26 runs across all 5 models.
