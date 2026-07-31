# experiments/

The benchmark runner and the raw logs it produces.

| Path | Purpose |
| --- | --- |
| [`run_benchmark.py`](run_benchmark.py) | Sweeps graph sizes × start users × models, scores every run, writes metrics + plots |
| `logs/` | Raw per-run records (`results.csv`) emitted by the evaluation logger (git-ignored) |

## What it does

For each graph size, `run_benchmark.py`:

1. regenerates the synthetic graph (deterministic, `seed=1337`),
2. picks start users — all planted-chain footholds plus N random users (some reachable,
   some not, to test whether the agent hallucinates a path where none exists),
3. runs the agent from each start, scores it against the ground-truth baseline, and logs
   real telemetry,

then prints the aggregate metrics, renders the scaling plots into [`results/`](../results/),
and restores the default graph.

```bash
python experiments/run_benchmark.py                                   # default sweep
python experiments/run_benchmark.py --sizes 150 350 600 --random 5    # custom sizes/starts
python experiments/run_benchmark.py --models openai/gpt-4o-mini anthropic/claude-3.5-haiku
```

Flags: `--sizes` (user counts per graph), `--random` (random starts per graph),
`--trials`, `--temperature`, `--models` (one or more, for model-vs-model comparison),
`--max-steps`, `--seed`, `--infra-retries`, `--from` (a real BloodHound export),
`--no-restore`.

## Getting a defensible number

The default sweep runs at **temperature 0**, which makes it reproducible but means extra
`--trials` are near-duplicates: they add no information about run-to-run variance. The
confidence intervals in `results/metrics.md` then describe variation *across start nodes*,
not across samples of the same case.

For a genuine variance estimate:

```bash
python experiments/run_benchmark.py --sizes 150 350 --random 5 --trials 5 --temperature 0.7
```

> **Not every model accepts a temperature.** Current Claude models (Opus 5, Sonnet 5, Opus 4.7/4.8, Fable 5) reject the parameter outright, so the backend drops it and those runs stay deterministic — `--trials` adds no variance there. The runner prints a warning naming the affected models; pick one that still accepts sampling if you need a variance sweep.

Two things to check before quoting the result:

- **The denominator.** The sweep prints `attempted N, scored M` per model at the end. Runs
  that die from exhausted credit or rate limits are excluded from the metrics (they aren't
  the agent being wrong), but a large exclusion means the surviving runs are a selected
  sample. `--infra-retries` (default 2) retries those failures rather than dropping them —
  raise it on a flaky connection.
- **The interval, not the point.** 100% over 11 runs is `100% [74.1–100]`. Overlapping
  intervals between two models mean the sweep did not separate them.

Each sweep archives its raw CSV and provenance (git SHA, models, temperature, seed, sizes,
attempted/scored counts) under [`results/runs/`](../results/runs/), so any published table
can be traced back to the runs behind it.

## Notes

- **Run one at a time.** A lock file (`.benchmark.lock`) prevents a second run from wiping
  the same database mid-sweep.
- LLM cost scales with (models × sizes × starts × trials × tool calls) — keep sweeps modest
  unless you've topped up API credit.
