# data/cypher/

Cypher — Neo4j's query language — for the **ground-truth answer key**.

| Path | Purpose |
| --- | --- |
| [`ground_truth/`](ground_truth/) | Shortest-path query from a starting user to any Domain Admin |

## Ground truth = the baseline

`ground_truth/shortest_path_to_da.cypher` is a parametrised shortest-path query over the
attack-relevant edge types. It plays two roles at once: it's the **answer key** the agent
is scored against, and it **is** the BloodHound rule-based comparison — the same kind of
"shortest path to Domain Admin" query BloodHound runs. For each scenario it yields the
path, its hop count, and (for the speed comparison) how long the query takes.

In practice the scoring harness computes this directly through the shared driver — see
[`src/ariadne/evaluation/score.py`](../../src/ariadne/evaluation/score.py) and the
`check_path_exists` tool — so this folder is the readable, standalone reference for the
same traversal.
