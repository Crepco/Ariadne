"""
Graph query tools exposed to the LLM agent.

Each function wraps a Cypher query so the agent never writes
Cypher directly. They all share the process-wide Neo4j driver
(see ``ariadne.db.get_driver``) — the driver is never closed here,
so a whole benchmark sweep reuses one connection pool instead of
opening and tearing one down on every tool call.
"""

from __future__ import annotations

import re

from ariadne.db import get_driver, run_read
from ariadne.inference import classify_hop
from ariadne.schema import (
    CANONICAL_EDGES,
    GOAL_GROUP,
    INFERENCE_PROPERTIES,
    TRAVERSABLE_EDGES,
)


def search_node(name_or_type: str, database: str | None = None):
    """
    Search for a node by name, partial name, or label.

    Examples:
        search_node("USER0001")
        search_node("DOMAIN ADMINS")
        search_node("Computer")
    """

    query = """
    MATCH (n)
    WHERE
        toUpper(n.name) CONTAINS toUpper($search)
        OR ANY(label IN labels(n)
               WHERE toUpper(label)=toUpper($search))
    RETURN
        labels(n) AS labels,
        n.name AS name,
        n.objectid AS objectid
    ORDER BY name
    LIMIT 25
    """

    return run_read(get_driver(), query, database=database, search=name_or_type)


def query_outbound_edges(objectid: str, database: str | None = None):
    """
    Return everything this node can reach/control.
    """

    query = """
    MATCH (n {objectid:$oid})-[r]->(m)
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

    query = """
    MATCH (n {objectid:$oid})
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

    query = """
    MATCH (n)-[r]->(m {objectid:$oid})
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
    """

    rel_filter = "|".join(TRAVERSABLE_EDGES)

    query = f"""
    MATCH (s {{objectid:$start}})
    MATCH (g {{objectid:$goal}})

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
def _short(name: str) -> str:
    """First label of a name (USER@DOM / HOST.DOM -> USER / HOST), upper-cased."""
    return re.split(r"[@.]", name or "")[0].upper()


def _resolve_names(driver, database, tokens: list[str]):
    """Map path tokens (names or object ids) to object ids, tolerating short names.

    Mirrors ``score.ScoringContext.resolve`` so the tool and the scorer agree on
    what a name points to. Returns ``(oids, props, goal_oid)`` where ``oids`` is a
    list aligned with ``tokens`` (``None`` where a token could not be resolved).
    """
    prop_cols = ", ".join(f"n.{p} AS {p}" for p in INFERENCE_PROPERTIES)
    rows = run_read(
        driver,
        f"MATCH (n) RETURN n.objectid AS oid, n.name AS name, {prop_cols}",
        database=database,
    )
    name_to_oid: dict[str, str] = {}
    oid_set: set[str] = set()
    props: dict[str, dict] = {}
    goal_oid = None
    for r in rows:
        oid, name = r["oid"], r["name"]
        if not oid:
            continue
        oid_set.add(oid)
        props[oid] = {p: r.get(p) for p in INFERENCE_PROPERTIES}
        if name:
            name_to_oid[name.upper()] = oid
            name_to_oid.setdefault(_short(name), oid)
            if name.upper().startswith(GOAL_GROUP + "@"):
                goal_oid = oid

    def resolve(tok: str):
        t = (tok or "").strip()
        if t in oid_set:
            return t
        return name_to_oid.get(t.upper())

    return [resolve(t) for t in tokens], props, goal_oid


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
    using the SAME edge-or-inference rule the scorer uses — so a path this tool
    calls valid is the path that will score as correct.
    """
    tokens = _parse_path_arg(path)
    if len(tokens) < 2:
        return {"valid": False, "reason": "A path needs at least two nodes (start -> ... -> DOMAIN ADMINS)."}

    driver = get_driver()
    resolved, props, goal_oid = _resolve_names(driver, database, tokens)

    unresolved = [t for t, o in zip(tokens, resolved) if o is None]
    if unresolved:
        return {"valid": False, "unresolved": unresolved,
                "reason": f"These names do not exist in the graph: {', '.join(unresolved)}. "
                          f"Use exact names returned by search_node."}

    # Canonical edge types between the specific (a,b) pairs on the path.
    pairs = list(zip(resolved, resolved[1:]))
    edge_type: dict[tuple[str, str], str] = {}
    rows = run_read(
        driver,
        "MATCH (a)-[r]->(b) WHERE a.objectid IN $oids AND b.objectid IN $oids "
        "AND type(r) IN $canon RETURN a.objectid AS a, b.objectid AS b, type(r) AS t",
        database=database,
        oids=resolved,
        canon=list(CANONICAL_EDGES),
    )
    for r in rows:
        edge_type[(r["a"], r["b"])] = r["t"]

    hops = []
    first_bad = None
    derived = 0
    for i, (a, b) in enumerate(pairs):
        kind = classify_hop(edge_type.get((a, b)), props, a, b, goal_oid)
        ok = kind is not None
        if kind and kind[0] == "inferred":
            derived += 1
        hops.append({"from": tokens[i], "to": tokens[i + 1],
                     "step": (kind[1] if kind else None), "valid": ok})
        if not ok and first_bad is None:
            first_bad = i

    reaches_goal = resolved[-1] == goal_oid
    valid = first_bad is None and reaches_goal
    out = {"valid": valid, "hops": hops, "derived_steps": derived, "reaches_goal": reaches_goal}
    if first_bad is not None:
        a_name, b_name = tokens[first_bad], tokens[first_bad + 1]
        out["reason"] = (
            f"Hop {a_name} -> {b_name} is NOT a real step (no canonical edge and no "
            f"inferred rule justifies it). You likely skipped a node between them — "
            f"re-check {a_name}'s outbound edges and properties."
        )
    elif not reaches_goal:
        out["reason"] = f"The path does not end at {GOAL_GROUP}; the last node must be DOMAIN ADMINS."
    return out
