# data/

Producing the graph the agent reasons over, and the ground-truth answer key it's scored against.

## Subfolders

| Path | Purpose |
| --- | --- |
| [`generator/`](generator/) | Seeded generator that fills Neo4j with a synthetic, structurally realistic AD graph |
| [`cypher/`](cypher/) | Ground-truth shortest-path Cypher — the answer key and BloodHound-equivalent baseline |
| `graphs/` | Generated snapshots (e.g. `planted_answer_key.json`), git-ignored |

## Pipeline

```
generator/  →  Neo4j  →  cypher/ground_truth (shortest paths)  →  answer key
```

## Why synthetic data

The graphs conform to the **BloodHound schema** — the same structure a real SharpHound
collection produces — so the agent faces a realistic problem while we keep two things a
live network can't give us: full control over graph size, and an exact ground truth to
score against. There is no data-collection step and no live network.
