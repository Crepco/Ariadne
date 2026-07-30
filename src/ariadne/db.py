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
from .schema import BASE_LABEL, BASE_ID_INDEX, NODE_LABELS

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

    The query runs in an explicit **READ** transaction (``execute_read``), so the
    *server* rejects any write clause. That matters because the chat assistant
    feeds LLM-authored Cypher through here: its keyword blocklist is a nicety for
    error messages, but this is the actual boundary. A plain ``session.run`` uses
    WRITE access mode and would happily execute ``MATCH (n) SET n.x = 1``.
    """
    if database is None:
        database = load_neo4j_config().database

    def _work(tx):
        return [record.data() for record in tx.run(query, **params)]

    with driver.session(database=database) as session:
        return session.execute_read(_work)


# --------------------------------------------------------------------------
# Schema setup + node upsert — shared by the generator and the ingest path
# --------------------------------------------------------------------------
# Derived from a node's name at write time so lookups never have to wrap the
# stored value in toUpper()/split(), which would rule out any index and force a
# scan of every node.
#   name_upper  the full name, upper-cased  (USER0001@ARIADNE.LOCAL)
#   short_name  the leading label           (USER0001)
_DERIVED_NAME_PROPS = (
    "n.name_upper = toUpper(coalesce(row.props.name, '')), "
    "n.short_name = split(split(toUpper(coalesce(row.props.name, '')), '@')[0], '.')[0]"
)


def node_upsert_query(label: str) -> str:
    """The ``UNWIND $rows``-shaped upsert for one node label.

    Every node also gets the shared :data:`~ariadne.schema.BASE_LABEL`, because a
    Neo4j property index is only usable when the pattern names a label — and our
    lookups are by object id, which is type-agnostic.
    """
    return (
        f"UNWIND $rows AS row MERGE (n:{label} {{objectid: row.objectid}}) "
        f"SET n:{BASE_LABEL}, n += row.props, {_DERIVED_NAME_PROPS}"
    )


def ensure_indexes(driver: Driver, database: str | None = None) -> None:
    """Create the constraints and indexes every query path depends on."""
    if database is None:
        database = load_neo4j_config().database
    statements = [
        # Uniqueness constraint per label doubles as an objectid index.
        *(f"CREATE CONSTRAINT {label.lower()}_objectid IF NOT EXISTS "
          f"FOR (n:{label}) REQUIRE n.objectid IS UNIQUE" for label in NODE_LABELS),
        # The one that matters for the agent's hot path: id lookups by :Base.
        f"CREATE INDEX {BASE_ID_INDEX} IF NOT EXISTS FOR (n:{BASE_LABEL}) ON (n.objectid)",
        # Name lookups used by search_node and verify_path.
        f"CREATE INDEX base_name_upper IF NOT EXISTS FOR (n:{BASE_LABEL}) ON (n.name_upper)",
        f"CREATE INDEX base_short_name IF NOT EXISTS FOR (n:{BASE_LABEL}) ON (n.short_name)",
    ]
    with driver.session(database=database) as session:
        for statement in statements:
            session.run(statement).consume()


def require_base_label(driver: Driver, database: str | None = None) -> None:
    """Fail loudly if the graph predates the shared ``:Base`` label.

    Every lookup is scoped to ``:Base`` so it can use an index. On a graph
    written before that label existed those queries match nothing — which would
    surface as an agent that mysteriously can't find any node, or an audit
    reporting zero findings on a graph full of them. A silently empty result is
    the worst possible failure here, so check once and say exactly what to run.
    """
    if database is None:
        database = load_neo4j_config().database
    rows = run_read(
        driver,
        f"MATCH (n) WITH count(n) AS total "
        f"OPTIONAL MATCH (b:{BASE_LABEL}) RETURN total, count(b) AS labelled",
        database=database,
    )
    if not rows:
        return
    total, labelled = rows[0]["total"], rows[0]["labelled"]
    if total > 0 and labelled == 0:
        raise RuntimeError(
            f"This graph has {total} nodes but none carry the ':{BASE_LABEL}' label, so every "
            "lookup would return nothing.\n"
            "It was written by an older version of Ariadne. Backfill it once (idempotent, "
            "no data loss):\n"
            "    python data/generator/migrate_base_label.py\n"
            "…or rebuild it: python data/generator/generate.py --wipe"
        )


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
