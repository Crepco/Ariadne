# src/ariadne/evaluation/

Scoring, logging, and metrics — turns raw agent runs into the numbers in the results table.

## Modules

| File | Role |
| --- | --- |
| `score.py` | Verifies the agent's proposed path **hop by hop** against the graph, and compares it to the ground-truth shortest path (the baseline). |
| `logger.py` | Appends one structured CSV row per run to `experiments/logs/results.csv`. |
| `metrics.py` | Aggregates the log into overall + per-graph-size tables (pandas). |
| `plots.py` | Renders the scaling plots into [`results/`](../../../results/) (matplotlib). |

## How a run is scored

1. Parse the ordered nodes the agent claims form the path.
2. Check **every consecutive hop** is a real edge in the graph, and that the chain reaches
   Domain Admins. A missing hop (or an unresolvable node) is a **hallucination**.
3. Compare to the ground-truth `shortestPath` for the same start (the BloodHound-equivalent
   baseline): is the goal reachable at all? Did the agent find an optimal-length path?
4. Runs that never produced an answer are marked *incomplete*; runs that failed for
   infrastructure reasons (e.g. the LLM was unreachable) are excluded from the metrics,
   never counted as hallucinations.

## Metrics

| Metric | Meaning |
| --- | --- |
| Correctness | Right answer (valid path when reachable; correctly declaring no path otherwise) |
| Valid-path rate | Proposed a real, connected path to Domain Admins |
| Hallucination rate | Proposed an edge/hop that doesn't exist |
| Optimal-length | Of solved runs, how many matched the shortest-path length |
| Tool-call efficiency & time | Queries and wall-clock time per run |
| Scaling | All of the above broken out by graph size |
| Gap vs. BloodHound | Reachable cases the agent missed |

Raw logs land in [`experiments/logs/`](../../../experiments/logs/) (git-ignored); derived
tables and figures in [`results/`](../../../results/).
