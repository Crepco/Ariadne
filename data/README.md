# data/

Everything about producing the graph the agent reasons over, and the ground-truth answer key it's scored against.

## Subfolders

| Path | Purpose |
| --- | --- |
| [`generator/`](generator/) | DBCreator — fills Neo4j with a synthetic, structurally realistic AD graph |
| [`cypher/`](cypher/) | Cypher scripts: ground-truth shortest paths (answer key) + optional planted misconfiguration chains |
| [`graphs/`](graphs/) | Exported graph snapshots / dumps for reproducibility (git-ignored) |

## The pipeline

```
generator/  →  Neo4j (infra/neo4j)  →  cypher/ground_truth  →  answer key
                                    →  cypher/planted        →  known-answer chains
```

## Why synthetic data is fine (for the paper)

- Evaluated on synthetic AD graphs conforming to the **BloodHound schema** — the same structure real collections use — which lets us control graph size and **guarantee ground truth**.
- Synthetic evaluation is standard practice for reproducible benchmarks: it removes organisation-specific noise and privacy concerns.
- "Validation on live-collected AD data" is listed explicitly as **future work**.
