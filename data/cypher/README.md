# data/cypher/

Cypher scripts — Neo4j's query language — that do two jobs: compute the **ground-truth answer key** and (optionally) **plant known misconfiguration chains**.

## Subfolders

| Path | Purpose |
| --- | --- |
| [`ground_truth/`](ground_truth/) | Shortest-path queries from a chosen starting user to any Domain Admin. This is the answer key **and** the BloodHound-equivalent baseline. |
| [`planted/`](planted/) | Optional `CREATE`/`MERGE` scripts that insert specific attack primitives (Kerberoasting hop, nested-group trap, etc.) whose answers you already know. |

## Ground truth = the baseline

The same shortest-path Cypher that produces the answer key **is** the BloodHound rule-based comparison. Record, for each scenario:

- the path(s) returned,
- the number of hops,
- how long the query takes (for the speed comparison).

## Planted chains (hybrid dataset)

Bulk realistic data from DBCreator **+** a handful of deliberately planted chains gives a hybrid dataset where you control some answers exactly. Recommended, but not required for a first result.

## To add

- `ground_truth/shortest_path_to_da.cypher` — parametrised start node → any Domain Admin.
- `planted/kerberoast_hop.cypher`, `planted/nested_group_trap.cypher`, etc.
- A short key mapping each planted scenario to its expected path.
