"""Thin Neo4j driver wrapper shared by the generator, tools, and scoring.

Nothing clever here — just a single place that knows how to open a driver from
config and run batched writes / reads, so the rest of the code never touches the
raw driver lifecycle.

The driver is a **process-wide singleton**. A Neo4j ``Driver`` owns a connection
pool and is designed to be created once and reused; it is thread-safe. Opening a
fresh driver per query (which the agent tools used to do, once per tool call)
means a new pool and — on Aura — a fresh TLS handshake and routing-table fetch
every time, which dominates the runtime of a benchmark sweep. ``get_driver()``
therefore returns the cached driver by default and callers must **not** close it;
it is closed once at interpreter exit (and can be closed explicitly via
``close_driver()``). Passing an explicit ``config`` opts out of the cache and
returns a fresh driver the caller owns.
"""

from __future__ import annotations

import atexit
import threading
from typing import Any, Iterable

from neo4j import Driver, GraphDatabase

from .config import Neo4jConfig, load_neo4j_config

# Process-wide cached driver, keyed by connection identity so a change of
# credentials (e.g. in tests) transparently rebuilds it.
_shared_driver: Driver | None = None
_shared_key: tuple[str, str, str] | None = None
_driver_lock = threading.Lock()


def get_driver(config: Neo4jConfig | None = None) -> Driver:
    """Return a Neo4j driver.

    With no ``config`` (the common case) this returns the cached, shared driver —
    do **not** call ``.close()`` on it; use :func:`close_driver` for teardown.
    With an explicit ``config`` it returns a fresh driver the caller owns and is
    responsible for closing.
    """
    if config is not None:
        return GraphDatabase.driver(config.uri, auth=(config.user, config.password))

    global _shared_driver, _shared_key
    cfg = load_neo4j_config()
    key = (cfg.uri, cfg.user, cfg.password)
    with _driver_lock:
        if _shared_driver is None or _shared_key != key:
            if _shared_driver is not None:
                _shared_driver.close()
            _shared_driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))
            _shared_key = key
        return _shared_driver


def close_driver() -> None:
    """Close the shared driver, if one is open. Safe to call repeatedly."""
    global _shared_driver, _shared_key
    with _driver_lock:
        if _shared_driver is not None:
            _shared_driver.close()
            _shared_driver = None
            _shared_key = None


atexit.register(close_driver)


def verify_connectivity(config: Neo4jConfig | None = None) -> str:
    """Ping the database. Returns the server agent string, or raises on failure."""
    cfg = config or load_neo4j_config()
    # Use a dedicated, caller-owned driver so this one-shot check never disturbs
    # the shared driver's lifecycle.
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
    driver: Driver, query: str, database: str | None = None, **params: Any
) -> list[dict[str, Any]]:
    """Run a read query and return all rows as plain dicts.

    ``database`` defaults to the configured ``NEO4J_DATABASE`` so callers that
    don't care (e.g. the agent tools) still hit the right database on Aura,
    where the database name is not ``neo4j``.
    """
    if database is None:
        database = load_neo4j_config().database
    with driver.session(database=database) as session:
        result = session.run(query, **params)
        return [record.data() for record in result]


def run_write_batches(
    driver: Driver,
    query: str,
    rows: Iterable[dict[str, Any]],
    *,
    database: str | None = None,
    batch_size: int = 1000,
) -> int:
    """Run a write query repeatedly over ``$rows`` in chunks. Returns row count.

    The query must reference an ``$rows`` parameter (typically ``UNWIND $rows AS
    row ...``). Batching keeps transactions small enough for Aura's limits.
    ``database`` defaults to the configured ``NEO4J_DATABASE``.
    """
    if database is None:
        database = load_neo4j_config().database
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
