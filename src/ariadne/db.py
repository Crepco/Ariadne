"""Thin Neo4j driver wrapper shared by the generator, tools, and scoring.

Nothing clever here — just a single place that knows how to open a driver from
config and run batched writes / reads, so the rest of the code never touches the
raw driver lifecycle.
"""

from __future__ import annotations

from typing import Any, Iterable

from neo4j import Driver, GraphDatabase

from .config import Neo4jConfig, load_neo4j_config


def get_driver(config: Neo4jConfig | None = None) -> Driver:
    """Open a Neo4j driver using the given (or environment-loaded) config."""
    cfg = config or load_neo4j_config()
    return GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))


def verify_connectivity(config: Neo4jConfig | None = None) -> str:
    """Ping the database. Returns the server agent string, or raises on failure."""
    cfg = config or load_neo4j_config()
    driver = get_driver(cfg)
    try:
        driver.verify_connectivity()
        with driver.session(database=cfg.database) as session:
            try:
                record = session.run(
                    "CALL dbms.components() YIELD name, versions "
                    "RETURN name + ' ' + versions[0] AS info LIMIT 1"
                ).single()
                return record["info"] if record else "connected"
            except Exception:
                # Some managed instances restrict dbms.components(); a plain
                # round-trip is enough to prove connectivity.
                session.run("RETURN 1").consume()
                return "connected"
    finally:
        driver.close()


def run_read(
    driver: Driver, query: str, database: str = "neo4j", **params: Any
) -> list[dict[str, Any]]:
    """Run a read query and return all rows as plain dicts."""
    with driver.session(database=database) as session:
        result = session.run(query, **params)
        return [record.data() for record in result]


def run_write_batches(
    driver: Driver,
    query: str,
    rows: Iterable[dict[str, Any]],
    *,
    database: str = "neo4j",
    batch_size: int = 1000,
) -> int:
    """Run a write query repeatedly over ``$rows`` in chunks. Returns row count.

    The query must reference an ``$rows`` parameter (typically ``UNWIND $rows AS
    row ...``). Batching keeps transactions small enough for Aura's limits.
    """
    rows = list(rows)
    total = 0
    with driver.session(database=database) as session:
        for start in range(0, len(rows), batch_size):
            chunk = rows[start : start + batch_size]

            def _work(tx, c=chunk):
                tx.run(query, rows=c).consume()

            session.execute_write(_work)
            total += len(chunk)
    return total
