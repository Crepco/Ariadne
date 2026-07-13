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
`--trials`, `--models` (one or more, for model-vs-model comparison), `--no-restore`.

## Notes

- **Run one at a time.** A lock file (`.benchmark.lock`) prevents a second run from wiping
  the same database mid-sweep.
- LLM cost scales with (models × sizes × starts × trials × tool calls) — keep sweeps modest
  unless you've topped up API credit. At temperature 0, extra `--trials` are near-duplicates.
