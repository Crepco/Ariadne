"""Backfill the shared ``:Base`` label and name lookup properties.

Graphs written before the ``:Base`` label existed have no label the object-id
index can attach to, so every agent tool call degrades to a full node scan. This
script brings such a graph up to date **in place** — no regeneration, no
re-ingest, no data loss.

It is idempotent: running it twice changes nothing the second time.

Usage (repo root, venv python)::

    python data/generator/migrate_base_label.py
    python data/generator/migrate_base_label.py --batch-size 5000   # huge graphs
"""

from __future__ import annotations

import argparse

from ariadne.config import load_neo4j_config
from ariadne.db import ensure_indexes, get_driver
from ariadne.schema import BASE_LABEL


def migrate(database: str | None = None, batch_size: int = 10_000) -> int:
    """Label every node ``:Base`` and derive its name lookup properties.

    Returns the number of nodes updated. Batched so a large graph doesn't build
    one enormous transaction.
    """
    if database is None:
        database = load_neo4j_config().database
    driver = get_driver()

    # Indexes first: creating them before the backfill means the writes populate
    # them as they go, rather than triggering one big index build afterwards.
    ensure_indexes(driver, database)

    total = 0
    with driver.session(database=database) as session:
        while True:
            result = session.run(
                f"MATCH (n) WHERE NOT n:{BASE_LABEL} OR n.name_upper IS NULL "
                "WITH n LIMIT $limit "
                f"SET n:{BASE_LABEL}, "
                "    n.name_upper = toUpper(coalesce(n.name, '')), "
                "    n.short_name = split(split(toUpper(coalesce(n.name, '')), '@')[0], '.')[0] "
                "RETURN count(n) AS c",
                limit=batch_size,
            ).single()
            updated = result["c"] if result else 0
            total += updated
            if updated == 0:
                break
            print(f"  … {total} nodes migrated")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch-size", type=int, default=10_000,
                    help="nodes per transaction (default: 10000)")
    args = ap.parse_args()

    cfg = load_neo4j_config()
    print(f"Migrating {cfg.uri} (database {cfg.database}) …")
    total = migrate(cfg.database, args.batch_size)
    print(f"Done: {total} node(s) updated." if total else "Nothing to do — already migrated.")


if __name__ == "__main__":
    main()
