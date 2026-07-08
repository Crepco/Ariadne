# experiments/

Where runs are *defined* and their raw output *lands*. The reproducible bridge between the code and the results.

## Layout

| Path | Purpose |
| --- | --- |
| [`configs/`](configs/) | One config per experiment: model, scenario(s), graph size, start node, goal, trial count, step budget |
| [`logs/`](logs/) | Raw per-run records emitted by the evaluation logger (git-ignored) |

## A scenario

A single trial = (model × graph × start node × goal). The full benchmark sweeps:

- **graph sizes** for the scaling curve (300 → 500 → 1,000 → 2,000+ nodes),
- optionally a **second model**,
- **repeated trials** per cell for variance.

> Cap trial counts to keep LLM API cost down — cost scales with (models × scenarios × trials × tool calls).

## Flow

```
configs/*  →  agent runs  →  logs/*  →  results/ (figures + tables)
```

## To add

- `configs/smoke.yaml` — the simplest known path, for first-light debugging.
- `configs/scaling.yaml` — the full graph-size sweep.
