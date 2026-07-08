# src/ariadne/evaluation/

Scoring, logging, and metrics — turns raw agent runs into the numbers that go in the paper.

## What it does

1. **Score** each proposed path against the graph (via `check_path_exists` / Cypher) — is every hop real? Does it reach a Domain Admin?
2. **Compare** against the ground-truth shortest path from [`data/cypher/ground_truth/`](../../../data/cypher/ground_truth/) (the BloodHound-equivalent baseline).
3. **Log** one structured record per run.

## Log record (one CSV/JSON row per run)

`model, scenario, graph_size, start_node, goal, proposed_path, num_tool_calls, wall_time_s, path_valid, matches_baseline, hallucinated_edge`

Raw logs land in [`experiments/logs/`](../../../experiments/logs/); derived tables/figures in [`results/`](../../../results/).

## Metrics computed

| Metric | Meaning |
| --- | --- |
| Path-correctness rate | % of runs where the proposed path is verified real |
| Hallucination rate | % of runs proposing an edge/hop that does not exist |
| Time-to-solution | Wall-clock time to the final answer |
| Tool-call efficiency | Queries used to reach a correct answer |
| Scaling behaviour | Correctness/time vs. graph size (300 → 2,000+) |
| Gap vs. BloodHound | Paths the agent finds that the queries miss, or vice versa |

## To add

- `score.py` — path validation + baseline comparison.
- `logger.py` — structured per-run record writer.
- `metrics.py` — aggregate the logs (pandas) and emit figures (matplotlib).
