"""
Graph query tools exposed to the LLM agent.

Each function wraps a Cypher query so the agent never writes
Cypher directly.
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

    driver = get_driver()

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

    try:
        return run_read(
            driver,
            query,
            database=database,
            search=name_or_type,
        )
    finally:
        driver.close()


def query_outbound_edges(objectid: str, database: str | None = None):
    """
    Return everything this node can reach/control.
    """

    driver = get_driver()

    query = """
    MATCH (n {objectid:$oid})-[r]->(m)
    RETURN
        type(r) AS relationship,
        labels(m) AS labels,
        m.name AS target,
        m.objectid AS objectid
    ORDER BY relationship,target
    """

    try:
        return run_read(
            driver,
            query,
            database=database,
            oid=objectid,
        )
    finally:
        driver.close()


def query_inbound_edges(objectid: str, database: str | None = None):
    """
    Return everything that can reach/control this node.
    """

    driver = get_driver()

    query = """
    MATCH (n)-[r]->(m {objectid:$oid})
    RETURN
        type(r) AS relationship,
        labels(n) AS labels,
        n.name AS source,
        n.objectid AS objectid
    ORDER BY relationship,source
    """

    try:
        return run_read(
            driver,
            query,
            database=database,
            oid=objectid,
        )
    finally:
        driver.close()


def check_path_exists(
    start_objectid: str,
    goal_objectid: str,
    database: str | None = None,
):
    """
    Verify whether an attack path exists between two objects.
    Returns the shortest path if one exists.
    """

    driver = get_driver()

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

    try:
        result = run_read(
            driver,
            query,
            database=database,
            start=start_objectid,
            goal=goal_objectid,
        )

        return result[0] if result else None

    finally:
        driver.close()