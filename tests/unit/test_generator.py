"""Offline tests for the synthetic-graph generator (no database)."""

from __future__ import annotations

import generate
from ariadne.schema import GOAL_GROUP, TRAVERSABLE_EDGES


def _build(**kw):
    return generate.build_graph(n_users=60, n_computers=12, n_groups=10, seed=1337, **kw)


def test_build_is_deterministic():
    a = _build()
    b = _build()
    assert [n["objectid"] for n in a["nodes"]] == [n["objectid"] for n in b["nodes"]]
    assert sorted(a["edges"]) == sorted(b["edges"])


def test_different_seed_changes_graph():
    a = generate.build_graph(n_users=60, n_computers=12, n_groups=10, seed=1337)
    b = generate.build_graph(n_users=60, n_computers=12, n_groups=10, seed=7)
    assert sorted(a["edges"]) != sorted(b["edges"])


def test_only_known_edge_types_are_emitted():
    graph = _build()
    allowed = set(TRAVERSABLE_EDGES)
    assert {etype for etype, _, _ in graph["edges"]} <= allowed


def test_node_objectids_are_unique():
    graph = _build()
    oids = [n["objectid"] for n in graph["nodes"]]
    assert len(oids) == len(set(oids))


def test_goal_group_exists_and_is_high_value():
    graph = _build()
    goal_nodes = [n for n in graph["nodes"] if n["objectid"] == graph["goal"]]
    assert len(goal_nodes) == 1
    assert goal_nodes[0]["props"]["name"].startswith(GOAL_GROUP + "@")
    assert goal_nodes[0]["props"]["highvalue"] is True


def test_planted_chains_are_reachable_and_declared():
    graph = _build()
    names = {p["name"] for p in graph["planted"]}
    assert names == {"forcechange_nested_genericall", "genericwrite_addmember_nested"}
    report = generate.solvability_report(graph)
    assert report["planted_chains_reachable"] is True


def test_solvability_report_shape():
    graph = _build()
    report = generate.solvability_report(graph, sample=40)
    assert 0 <= report["solvable_users"] <= report["sampled_users"] <= 40
    assert 0.0 <= report["solvable_fraction"] <= 1.0


def test_no_plant_option_leaves_no_planted_chains():
    graph = generate.build_graph(n_users=40, n_computers=8, n_groups=8, seed=1337, plant=False)
    assert graph["planted"] == []
