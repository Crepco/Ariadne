"""Offline tests for the synthetic-graph generator (no database)."""

from __future__ import annotations

import generate
from ariadne.schema import ADVANCED_EDGES, CANONICAL_EDGES, GOAL_GROUP, TRAVERSABLE_EDGES


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
    assert names == {
        "forcechange_nested_genericall",
        "genericwrite_addmember_nested",
        "kerberoast_nested_genericall",
    }
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


# --- advanced primitives / BloodHound-blind chain --------------------------
def _edge_types(graph):
    return {etype for etype, _, _ in graph["edges"]}


def test_advanced_edges_are_emitted():
    # A graph big enough to contain SPN users and unconstrained-delegation hosts.
    graph = generate.build_graph(n_users=200, n_computers=40, n_groups=20, seed=1337)
    present = _edge_types(graph)
    assert "Kerberoastable" in present
    assert set(ADVANCED_EDGES) <= set(TRAVERSABLE_EDGES)


def test_advanced_chain_is_planted_and_flagged():
    graph = _build()
    advanced = [p for p in graph["planted"] if p.get("advanced")]
    assert len(advanced) == 1
    chain = advanced[0]
    assert chain["name"] == "kerberoast_nested_genericall"
    assert chain["edges"][0] == "Kerberoastable"


def test_advanced_chain_is_bloodhound_blind_but_truly_reachable():
    graph = _build()
    chain = next(p for p in graph["planted"] if p.get("advanced"))
    start, goal = chain["start"], graph["goal"]
    truth = generate._adjacency(graph)                       # all edges
    canonical = generate._adjacency(graph, CANONICAL_EDGES)  # BloodHound baseline
    assert generate._reachable(truth, start, goal) is True
    assert generate._reachable(canonical, start, goal) is False


def test_solvability_report_flags_advanced_gap():
    graph = _build()
    report = generate.solvability_report(graph)
    assert report["advanced_chains_bloodhound_blind"] is True
    assert report["canonical_solvable_users"] <= report["solvable_users"]
    assert report["advanced_only_users"] >= 0
