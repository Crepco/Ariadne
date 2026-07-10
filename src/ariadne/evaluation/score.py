"""
Evaluation utilities.

Responsible for:
1. Validating whether the agent's proposed attack path exists.
2. Comparing it against the ground-truth shortest path.
"""

from __future__ import annotations

from ariadne.tools import check_path_exists


def path_is_valid(start_oid: str, goal_oid: str) -> bool:
    """
    Returns True if a valid attack path exists.
    """

    result = check_path_exists(start_oid, goal_oid)

    if result is None:
        return False

    return result["exists"]


def compare_to_ground_truth(start_oid: str, goal_oid: str):
    """
    Returns the shortest ground-truth path between
    the start node and Domain Admins.
    """

    result = check_path_exists(start_oid, goal_oid)

    if result is None:
        return None

    return {
        "nodes": result["nodes"],
        "edges": result["edges"],
        "hops": result["hops"],
    }


def score_run(start_oid: str, goal_oid: str):
    """
    Score one agent run.

    Returns a dictionary that can later be logged.
    """

    result = check_path_exists(start_oid, goal_oid)

    if result is None:
        return {
            "path_valid": False,
            "hallucinated_edge": True,
            "hops": -1,
            "nodes": [],
            "edges": [],
        }

    return {
        "path_valid": result["exists"],
        "hallucinated_edge": not result["exists"],
        "hops": result["hops"],
        "nodes": result["nodes"],
        "edges": result["edges"],
    }