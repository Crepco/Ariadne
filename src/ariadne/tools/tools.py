"""
Graph query tools exposed to the LLM agent.

Each function wraps a Cypher query so the agent never writes
Cypher directly. They all share the process-wide Neo4j driver
(see ``ariadne.db.get_driver``) — the driver is never closed here,
so a whole benchmark sweep reuses one connection pool instead of
opening and tearing one down on every tool call.

Every node lookup goes through the shared ``:Base`` label (see
``schema.BASE_LABEL``) so Neo4j can seek an index instead of scanning every node
in the graph. On a synthetic 200-node graph the difference is invisible; on a
real BloodHound collection it is the difference between working and not.
"""

from __future__ import annotations

import re

from ariadne.db import get_driver, run_read
from ariadne.inference import classify_hop
from ariadne.resolve import NameIndex, short_name
from ariadne.schema import (
    BASE_LABEL,
    CANONICAL_EDGES,
    GOAL_GROUP,
    INFERENCE_PROPERTIES,
    TRAVERSABLE_EDGES,
)
from ariadne.verify import as_tool_result, verify_walk

# Cap on how many nodes a name search returns to the agent.
SEARCH_LIMIT = 25

# Uppercase name, falling back to computing it when the graph predates the
# derived ``name_upper`` property. Only ever used in queries that scan anyway —
# an indexed seek must read the bare property, or the index can't be used.
_NAME_UPPER = "coalesce(n.name_upper, toUpper(n.name))"
_SHORT_NAME = ("coalesce(n.short_name, "
               "split(split(toUpper(coalesce(n.name, '')), '@')[0], '.')[0])")


def search_node(name_or_type: str, database: str | None = None):
    """
    Search for a node by name, partial name, or label.

    Tries the cheap, indexed lookups first (exact name, exact object id, label)
    and only falls back to a substring scan when those miss — so the common case
    of "resolve this name" is a seek rather than a full scan of the graph.

    Examples:
        search_node("USER0001")
        search_node("DOMAIN ADMINS")
        search_node("Computer")
    """
    driver = get_driver()
    term = (name_or_type or "").strip()
    if not term:
        return []

    # 1. Exact name / object id / short name — all index-backed on :Base.
    exact = run_read(
        driver,
        f"MATCH (n:{BASE_LABEL}) "
        "WHERE n.objectid = $term OR n.name_upper = $upper OR n.short_name = $upper "
        "RETURN labels(n) AS labels, n.name AS name, n.objectid AS objectid "
        f"ORDER BY name LIMIT {SEARCH_LIMIT}",
        database=database,
        term=term,
        upper=term.upper(),
    )
    if exact:
        return exact

    # 2. Label match (e.g. "Computer") — a label scan, still far cheaper than
    #    a property scan over every node.
    label = next((l for l in ("Domain", "User", "Group", "Computer")
                  if l.upper() == term.upper()), None)
    if label:
        return run_read(
            driver,
            f"MATCH (n:{label}) RETURN labels(n) AS labels, n.name AS name, "
            f"n.objectid AS objectid ORDER BY name LIMIT {SEARCH_LIMIT}",
            database=database,
        )

    # 3. Substring fallback — inherently a scan, so the coalesce costs nothing
    #    here and keeps the tool working on a graph written before name_upper
    #    existed (see data/generator/migrate_base_label.py). The seek above
    #    deliberately reads the raw property instead, since wrapping it would
    #    rule out the index.
    return run_read(
        driver,
        f"MATCH (n:{BASE_LABEL}) WHERE {_NAME_UPPER} CONTAINS $upper "
        "RETURN labels(n) AS labels, n.name AS name, n.objectid AS objectid "
        f"ORDER BY name LIMIT {SEARCH_LIMIT}",
        database=database,
        upper=term.upper(),
    )


def query_outbound_edges(objectid: str, database: str | None = None):
    """
    Return everything this node can reach/control.
    """

    query = f"""
    MATCH (n:{BASE_LABEL} {{objectid:$oid}})-[r]->(m)
    RETURN
        type(r) AS relationship,
        labels(m) AS labels,
        m.name AS target,
        m.objectid AS objectid
    ORDER BY relationship,target
    """

    return run_read(get_driver(), query, database=database, oid=objectid)


def get_node_properties(objectid: str, database: str | None = None):
    """
    Return a node's properties — including the ones that enable *inferred*
    attack steps that are NOT edges:
      hasspn / crackable       -> a kerberoastable, weak-password service account
      roastable_target         -> (on a host) the object id of a crackable account
                                  it exposes; reaching the host lets you roast it
      cred_target              -> (on a host/GPO) the object id of an account whose
                                  plaintext creds it leaks; reach it and become them
      unconstraineddelegation  -> (on a host) coerce a login for domain dominance
      esc1                     -> (on a host/CA) a misconfigured cert template lets
                                  you forge a cert for anyone -> domain dominance
    """

    query = f"""
    MATCH (n:{BASE_LABEL} {{objectid:$oid}})
    RETURN
        labels(n) AS labels,
        n.name AS name,
        n.objectid AS objectid,
        n.hasspn AS hasspn,
        n.crackable AS crackable,
        n.roastable_target AS roastable_target,
        n.cred_target AS cred_target,
        n.unconstraineddelegation AS unconstraineddelegation,
        n.esc1 AS esc1,
        n.admincount AS admincount,
        n.highvalue AS highvalue,
        n.is_dc AS is_dc,
        n.enabled AS enabled
    """

    rows = run_read(get_driver(), query, database=database, oid=objectid)
    return rows[0] if rows else None


def query_inbound_edges(objectid: str, database: str | None = None):
    """
    Return everything that can reach/control this node.
    """

    query = f"""
    MATCH (n)-[r]->(m:{BASE_LABEL} {{objectid:$oid}})
    RETURN
        type(r) AS relationship,
        labels(n) AS labels,
        n.name AS source,
        n.objectid AS objectid
    ORDER BY relationship,source
    """

    return run_read(get_driver(), query, database=database, oid=objectid)


def check_path_exists(
    start_objectid: str,
    goal_objectid: str,
    database: str | None = None,
):
    """
    Verify whether an attack path exists between two objects.
    Returns the shortest path if one exists.

    Takes TWO object ids, so the agent must call it with an object input::

        {"action": "check_path_exists",
         "input": {"start_objectid": "S-1-…-1105", "goal_objectid": "S-1-…-512"}}
    """

    rel_filter = "|".join(TRAVERSABLE_EDGES)

    query = f"""
    MATCH (s:{BASE_LABEL} {{objectid:$start}})
    MATCH (g:{BASE_LABEL} {{objectid:$goal}})

    OPTIONAL MATCH
        p = shortestPath((s)-[:{rel_filter}*1..15]->(g))

    RETURN
        CASE
            WHEN p IS NULL THEN false
            ELSE true
        END AS exists,

        CASE
            WHEN p IS NULL THEN []
            ELSE [n IN nodes(p) | n.name]
        END AS nodes,

        CASE
            WHEN p IS NULL THEN []
            ELSE [r IN relationships(p) | type(r)]
        END AS edges,

        CASE
            WHEN p IS NULL THEN -1
            ELSE length(p)
        END AS hops
    """

    result = run_read(
        get_driver(),
        query,
        database=database,
        start=start_objectid,
        goal=goal_objectid,
    )

    return result[0] if result else None


# --------------------------------------------------------------------------
# verify_path — self-check a proposed path before finishing
# --------------------------------------------------------------------------
def _prop_cols(var: str) -> str:
    """``n.hasspn AS hasspn, …`` for a given Cypher variable.

    Takes the variable explicitly because these columns are selected under two
    different aliases (the token match binds ``n``, the goal lookup binds ``g``);
    hard-coding ``n.`` made the goal query a syntax error that only fired when a
    path failed to name Domain Admins.
    """
    return ", ".join(f"{var}.{p} AS {p}" for p in INFERENCE_PROPERTIES)


def _index_for_tokens(driver, database, tokens: list[str]) -> NameIndex:
    """Build a :class:`NameIndex` covering just the nodes a path mentions.

    This used to load the ENTIRE graph (``MATCH (n) RETURN …``) on every single
    ``verify_path`` call. A path is at most a handful of nodes, so we fetch only
    the candidates for its tokens (by object id, full name, or short name) plus
    the goal node — turning an O(V) scan per call into an O(path) lookup.
    """
    wanted = [t.strip() for t in tokens if t and t.strip()]
    uppers = sorted({t.upper() for t in wanted} | {short_name(t) for t in wanted})

    # The indexed columns first (so Neo4j can seek), then the computed fallbacks
    # so a graph written before those properties existed still resolves — just
    # by scanning. Correctness must not depend on having run the migration.
    rows = run_read(
        driver,
        f"MATCH (n:{BASE_LABEL}) "
        "WHERE n.objectid IN $oids OR n.name_upper IN $uppers OR n.short_name IN $uppers "
        f"   OR {_NAME_UPPER} IN $uppers OR {_SHORT_NAME} IN $uppers "
        f"RETURN n.objectid AS oid, n.name AS name, {_prop_cols('n')}",
        database=database,
        oids=wanted,
        uppers=uppers,
    )
    index = NameIndex.from_rows(rows)

    # The goal anchors the unconstrained-delegation / ESC1 rules, so look it up
    # explicitly rather than hoping the agent's path already named it.
    if index.goal_oid is None:
        goal_rows = run_read(
            driver,
            f"MATCH (g:{BASE_LABEL}:Group) WHERE g.name STARTS WITH $p "
            f"RETURN g.objectid AS oid, g.name AS name, {_prop_cols('g')} LIMIT 1",
            database=database,
            p=f"{GOAL_GROUP}@",
        )
        for row in goal_rows:
            index.add(row["oid"], row["name"], {p: row.get(p) for p in INFERENCE_PROPERTIES})
        index.finalize()
    return index


def _edge_types_between(driver, database, oids: list[str]) -> dict[tuple[str, str], str]:
    """Canonical edge types among a small set of nodes, as ``(a, b) -> type``."""
    present = [o for o in oids if o]
    if len(present) < 2:
        return {}
    rows = run_read(
        driver,
        f"MATCH (a:{BASE_LABEL})-[r]->(b:{BASE_LABEL}) "
        "WHERE a.objectid IN $oids AND b.objectid IN $oids AND type(r) IN $canon "
        "RETURN a.objectid AS a, b.objectid AS b, type(r) AS t",
        database=database,
        oids=present,
        canon=list(CANONICAL_EDGES),
    )
    return {(r["a"], r["b"]): r["t"] for r in rows}


def _parse_path_arg(path) -> list[str]:
    """Accept a JSON-ish list, an arrow string 'A -> B -> DA', or a real list."""
    if isinstance(path, (list, tuple)):
        return [str(t).strip() for t in path if str(t).strip()]
    text = str(path or "")
    parts = re.split(r"->|=>|→|,", text)
    return [p.strip().strip("[]\"' ") for p in parts if p.strip().strip("[]\"' ")]


def verify_path(path, database: str | None = None):
    """Check whether an ordered path is a REAL edge-or-inference chain to the goal.

    Pass the node NAMES in order (as an arrow string ``"A -> B -> DOMAIN ADMINS"``
    or a JSON list). Every consecutive step must be either a canonical **edge** in
    the graph or a property-**inferred** step; the goal must be DOMAIN ADMINS. The
    result names the FIRST broken hop so you can fix it (usually a skipped node),
    using the SAME walk the scorer uses (``ariadne.verify.verify_walk``) — so a
    path this tool calls valid is the path that will score as correct.
    """
    tokens = _parse_path_arg(path)
    if len(tokens) < 2:
        return {"valid": False,
                "reason": "A path needs at least two nodes (start -> ... -> DOMAIN ADMINS)."}

    driver = get_driver()
    index = _index_for_tokens(driver, database, tokens)
    resolved, unknown, ambiguous = index.resolve_all(tokens)
    edge_type = _edge_types_between(driver, database, resolved)

    record = verify_walk(
        tokens,
        resolved,
        hop_kind=lambda a, b: classify_hop(
            edge_type.get((a, b)), index.props, a, b, index.goal_oid
        ),
        goal_oid=index.goal_oid,
        unknown=unknown,
        ambiguous=ambiguous,
    )
    return as_tool_result(record)
