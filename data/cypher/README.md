# data/cypher/

Cypher — Neo4j's query language — for the **ground-truth answer key**.

| Path | Purpose |
| --- | --- |
| [`ground_truth/`](ground_truth/) | Shortest-path query from a starting user to any Domain Admin |

## Ground truth = the baseline

`ground_truth/shortest_path_to_da.cypher` is a parametrised shortest-path query over the 
**canonical** attack edges (`schema.CANONICAL_EDGES`). It **is** the BloodHound rule-based
comparison — the same kind of "shortest path to Domain Admin" query BloodHound runs.

Scoring distinguishes two reachability notions (see
[`src/ariadne/evaluation/score.py`](../../src/ariadne/evaluation/score.py)):

- **True reachability** — shortest path over *all* attack edges, canonical **plus** advanced
  tradecraft (`schema.ADVANCED_EDGES`, e.g. `Kerberoastable`). This is the answer key the
  agent is actually scored against.
- **BloodHound reachability** — the canonical-only query above.

The gap between them is the interesting part: when the agent finds a *real* path that the
canonical query can't (`beats_bloodhound`), it has done something the rule-based baseline
cannot. The scoring harness computes both directly through the shared driver, so this folder
is the readable, standalone reference for the canonical baseline traversal.
