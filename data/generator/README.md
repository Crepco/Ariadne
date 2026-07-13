# data/generator/

The synthetic-graph generator: fills Neo4j with a randomized-but-realistic AD forest
(users, groups, computers + the attack-relevant edges between them) following the
BloodHound schema, plus a verifier that computes the ground-truth answer key.

## Files

| File | Role |
| --- | --- |
| `generate.py` | Build the graph in memory and write it to Neo4j. Also runs an offline `--dry-run` solvability check with no database. |
| `verify.py` | Confirm node/edge counts loaded, then compute ground-truth shortest paths to Domain Admins. |

Shared schema / DB / config live in the `ariadne` package under [`../../src/ariadne/`](../../src/ariadne/).

## Usage

```bash
# From the repo root, with the venv active and .env filled in.

python data/generator/generate.py --dry-run   # build in memory, report solvability, no DB
python data/generator/generate.py --wipe       # generate the default ~400-node graph into Neo4j
python data/generator/verify.py                # confirm it loaded + print ground-truth attack paths

# A larger graph for the scaling curve:
python data/generator/generate.py --users 1500 --computers 300 --groups 150 --wipe
```

Flags: `--users --computers --groups --density --seed --domain`, `--no-plant`
(skip planted chains), `--wipe` (clear the DB first), `--dry-run` (no database write).

## Design notes

- **Deterministic.** Fully seeded — the same `--seed` (default `1337`) yields the same graph, so results are reproducible.
- **Modern Cypher, no dependencies.** Emits plain Cypher with no APOC/admin procedures, so it runs on Neo4j 5.x and Aura out of the box.
- **Random relationships, computed answers.** Edges are random, so we never hand-pick the solution — `verify.py` derives the ground-truth path *after* generation with the same `shortestPath` BloodHound uses.

## Planted chains

By default the generator also inserts two deterministic attack chains whose answers are
known in advance and writes them to `data/graphs/planted_answer_key.json` — a hybrid of
realistic random bulk plus a few hand-verified paths. Disable with `--no-plant`.
