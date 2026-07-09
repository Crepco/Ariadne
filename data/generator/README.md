# data/generator/

The synthetic-graph generator: fills Neo4j with a randomized-but-realistic AD
forest (users, groups, computers + the attack-relevant edges between them),
following the BloodHound schema.

## Why our own generator (not DBCreator)

The plan names DBCreator (michiellemmens fork) as the standard tool, with "a
small hand-written Cypher graph-insert script" as the sanctioned fallback. We use
the fallback as the primary path, deliberately:

- **Neo4j 5.x / Aura compatibility** — DBCreator targets older Neo4j and commonly
  breaks on 5.x (the exact class of error the plan warns about). Our generator
  emits plain, modern Cypher with no APOC/admin dependencies, so it runs on Aura.
- **Reproducibility** — it's fully seeded: the same `--seed` yields the same graph.
- **Control** — we set the schema, edge density, and can plant known chains.

Relationships are still *random*, so we never hand-pick the answer. The
ground-truth path is computed **after** generation by `verify.py` using the same
Cypher `shortestPath` BloodHound uses.

## Files

| File | Role |
| --- | --- |
| `generate.py` | Build the graph (in memory) and write it to Neo4j. Also does an offline `--dry-run` solvability check with no database. |
| `verify.py` | Confirm counts loaded, then compute ground-truth shortest paths to Domain Admins (the answer key). |

Shared schema/DB/config live in the `ariadne` package under [`../../src/ariadne/`](../../src/ariadne/).

## Usage

```bash
# From the repo root, with the venv active and .env filled in.

# 1. Offline sanity check — build in memory, report solvability, no DB needed:
python data/generator/generate.py --dry-run

# 2. Generate the default ~400-node graph and write it to Neo4j:
python data/generator/generate.py --wipe

# 3. Confirm it loaded and see ground-truth attack paths:
python data/generator/verify.py

# Larger graph for the scaling curve:
python data/generator/generate.py --users 1500 --computers 300 --groups 150 --wipe
```

Key flags: `--users --computers --groups --density --seed --domain`,
`--no-plant` (skip planted chains), `--wipe` (clear the DB first),
`--dry-run` (no database write).

## Planted chains

By default the generator inserts two deterministic attack chains whose answers we
already know, and writes them to `data/graphs/planted_answer_key.json`. This gives
a hybrid dataset: realistic random bulk + a handful of hand-verified paths. Use
`--no-plant` to disable.
