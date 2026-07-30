"""Verify a generated graph in Neo4j and compute ground-truth attack paths.

After generate.py has written a graph, run this to:
  1. confirm node/edge counts loaded correctly, and
  2. compute the shortest path from sample users to Domain Admins over the
     canonical edges — i.e. the BloodHound-equivalent baseline path. (Property-
     inferred steps are not edges, so they don't appear here; TRUE reachability
     that includes inference is computed by the scorer — see evaluation/score.py
     and ariadne/inference.py.)

Usage (repo root, venv active)::

    python data/generator/verify.py
    python data/generator/verify.py --samples 10
"""

from __future__ import annotations

import argparse

from ariadne.db import get_driver, run_read
from ariadne.schema import BASE_LABEL, GOAL_GROUP, TRAVERSABLE_EDGES


def counts(driver, database: str = "neo4j") -> None:
    print("Node counts by label:")
    # Every node also carries the shared :Base label (it exists so id lookups can
    # use an index); skip it here so the census still reports one row per node.
    for row in run_read(
        driver,
        "MATCH (n) UNWIND labels(n) AS label WITH label WHERE label <> $base "
        "RETURN label, count(*) AS n ORDER BY label",
        database=database,
        base=BASE_LABEL,
    ):
        print(f"  {row['label']:<10} {row['n']}")

    print("Edge counts by type:")
    for row in run_read(
        driver,
        "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n ORDER BY t",
        database=database,
    ):
        print(f"  {row['t']:<22} {row['n']}")


def goal_objectid(driver, database: str = "neo4j") -> str | None:
    rows = run_read(
        driver,
        "MATCH (g:Group) WHERE g.name STARTS WITH $prefix RETURN g.objectid AS oid",
        database=database,
        prefix=f"{GOAL_GROUP}@",
    )
    return rows[0]["oid"] if rows else None


def traversable_rel_filter(driver, database: str = "neo4j") -> str:
    """Build the ``A|B|C`` filter from attack edges that actually exist in the DB.

    Restricting to present relationship types keeps Neo4j from warning about
    edge types the current graph happens not to contain.
    """
    present = {
        row["t"]
        for row in run_read(driver, "CALL db.relationshipTypes() YIELD relationshipType AS t RETURN t", database=database)
    }
    usable = [e for e in TRAVERSABLE_EDGES if e in present]
    return "|".join(usable)


def shortest_path(driver, start_oid: str, goal_oid: str, rel: str, database: str = "neo4j"):
    """Return the ground-truth shortest attack path, or None if unreachable."""
    query = f"""
    MATCH (s:{BASE_LABEL} {{objectid: $start}}), (g:{BASE_LABEL} {{objectid: $goal}})
    MATCH p = shortestPath((s)-[:{rel}*1..15]->(g))
    RETURN [n IN nodes(p) | n.name] AS nodes,
           [r IN relationships(p) | type(r)] AS edges,
           length(p) AS hops
    """
    rows = run_read(driver, query, database=database, start=start_oid, goal=goal_oid)
    return rows[0] if rows else None


def sample_ground_truth(driver, goal_oid: str, samples: int, database: str = "neo4j") -> None:
    rel = traversable_rel_filter(driver, database=database)
    # Prefer planted starts first (known answers), then random users.
    planted = run_read(
        driver,
        "MATCH (u:User) WHERE u.planted = true RETURN u.objectid AS oid, u.name AS name",
        database=database,
    )
    randoms = run_read(
        driver,
        "MATCH (u:User) WHERE coalesce(u.planted, false) = false "
        "RETURN u.objectid AS oid, u.name AS name ORDER BY rand() LIMIT $k",
        database=database,
        k=samples,
    )

    print("\nGround-truth shortest paths to Domain Admins:")
    solved = 0
    for label, users in (("planted", planted), ("random", randoms)):
        for u in users:
            path = shortest_path(driver, u["oid"], goal_oid, rel, database=database)
            if path:
                solved += 1
                chain = " -> ".join(
                    f"{n} =[{e}]=>" if i < len(path["edges"]) else n
                    for i, (n, e) in enumerate(
                        zip(path["nodes"], path["edges"] + [None])
                    )
                )
                print(f"  [{label}] {u['name']}  ({path['hops']} hops)")
                print(f"      {chain}")
            else:
                print(f"  [{label}] {u['name']}  -> no path")
    total = len(planted) + len(randoms)
    print(f"\n{solved}/{total} sampled users have a verified path to Domain Admins.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", type=int, default=5, help="random users to trace")
    args = ap.parse_args()

    from ariadne.config import load_neo4j_config

    db = load_neo4j_config().database
    driver = get_driver()  # shared process-wide driver; closed at interpreter exit
    counts(driver, database=db)
    goal = goal_objectid(driver, database=db)
    if not goal:
        print(f"\nCould not find the {GOAL_GROUP} group — was the graph generated?")
        return
    sample_ground_truth(driver, goal, args.samples, database=db)


if __name__ == "__main__":
    main()
