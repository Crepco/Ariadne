"""Offline tests for the property-based inference oracle."""

from __future__ import annotations

from ariadne.inference import INFERENCE_RULES, justifies_hop, true_reachable


PROPS = {
    "host": {"roastable_target": "svc"},
    "svc": {"hasspn": True, "crackable": True},
    "deleg": {"unconstraineddelegation": True},
    "plain": {},
}


def test_justifies_roast_from_exposing_host():
    assert justifies_hop(PROPS, "host", "svc", "DA") == "Kerberoast"


def test_justifies_delegation_to_goal_only():
    assert justifies_hop(PROPS, "deleg", "DA", "DA") == "UnconstrainedDelegation"
    # delegation only justifies a hop to the GOAL, not to an arbitrary node
    assert justifies_hop(PROPS, "deleg", "other", "DA") is None


def test_no_rule_for_plain_hop():
    assert justifies_hop(PROPS, "plain", "svc", "DA") is None  # only host exposes svc
    assert justifies_hop(PROPS, "host", "other", "DA") is None


def test_rule_names_are_documented():
    assert {"Kerberoast", "UnconstrainedDelegation"} <= set(INFERENCE_RULES)


def test_true_reachable_finds_inferred_path_canonical_bfs_cannot():
    # start -AdminTo-> host -(roast, inferred)-> svc -MemberOf-> grp -GenericAll-> DA
    adjacency = {"start": ["host"], "svc": ["grp"], "grp": ["DA"]}
    reachable, hops = true_reachable(adjacency, PROPS, "start", "DA")
    assert reachable is True
    assert hops == 4
    # canonical-only reachability (no inferred jumps) cannot get past the host
    canonical_only, _ = true_reachable({"start": ["host"]}, {}, "start", "DA")
    assert canonical_only is False


def test_true_reachable_delegation_jump():
    adjacency = {"start": ["deleg"]}
    reachable, hops = true_reachable(adjacency, PROPS, "start", "DA")
    assert reachable is True
    assert hops == 2  # start -> deleg -> (inferred) DA


def test_true_reachable_unreachable():
    reachable, hops = true_reachable({"start": ["plain"]}, PROPS, "start", "DA")
    assert reachable is False
    assert hops == -1
