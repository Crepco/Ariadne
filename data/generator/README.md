# data/generator/

The synthetic-graph generator: **DBCreator** from the BloodHound-Tools project. It connects to the Neo4j instance and generates a randomized AD dataset directly inside it — no Windows, no collection step. You control the size (e.g. 500 nodes, 2,000 nodes) and it builds users, groups, computers, and the relationship edges between them.

## Setup (planned)

Use the maintained fork — the original DBCreator has a known bug in its `generate` command that many people hit:

- **Fork:** `michiellemmens/DBCreator` (GitHub). Use this, or keep it as a fallback if the original throws errors.
- **Requirements:** Python 3.7+, the `neo4j` driver, a running Neo4j instance ([`../../infra/neo4j/`](../../infra/neo4j/)).

> Clone the fork into this directory (or add it as a submodule) rather than committing a copy — pin the commit you used in a note here for reproducibility. **Verify the current state of the fork before Day 1.**

## Why random relationships are fine

DBCreator generates **random** relationships, so you don't hand-pick "the answer is path X." That's a feature, not a bug: the ground-truth answer is computed **after** generation, directly from the graph, using the same Cypher shortest-path queries BloodHound uses ([`../cypher/ground_truth/`](../cypher/ground_truth/)). Random paths are arguably better than hand-tuned ones — they aren't accidentally biased to be easy.

## Fallback

Keep a small hand-written Cypher graph-insert script as a backup in case the generator needs patching for your Neo4j version. A starting point lives in [`../cypher/planted/`](../cypher/planted/).

## To add

- `generate.py` / config or a documented invocation of the fork's CLI.
- `NODE_COUNTS` presets for the scaling curve (300 → 500 → 1,000 → 2,000+).
- A note recording the exact fork commit + Neo4j version used.
