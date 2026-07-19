"""
Graph query tools exposed to the LLM agent.

Each function wraps a Cypher query so the agent never writes
Cypher directly. They all share the process-wide Neo4j driver
(see ``ariadne.db.get_driver``) — the driver is never closed here,
so a whole benchmark sweep reuses one connection pool instead of
opening and tearing one down on every tool call.
"""

from __future__ import annotations

from ariadne.db import get_driver, run_read
from ariadne.schema import TRAVERSABLE_EDGES


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
      unconstraineddelegation  -> (on a host) coerce a login for domain dominance
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
        n.unconstraineddelegation AS unconstraineddelegation,
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
