"""Offline tests for the property-based inference oracle."""

from __future__ import annotations

import random

from ariadne.inference import (
    INFERENCE_RULES,
    classify_hop,
    justifies_hop,
    reverse_reachable,
    true_reachable,
)


PROPS = {
    "host": {"roastable_target": "svc"},
    "svc": {"hasspn": True, "crackable": True},
    "deleg": {"unconstraineddelegation": True},
    "credhost": {"cred_target": "acct"},
    "ca": {"esc1": True},
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


def test_justifies_credential_exposure_from_leaking_host():
    assert justifies_hop(PROPS, "credhost", "acct", "DA") == "CredentialExposure"
    assert justifies_hop(PROPS, "credhost", "other", "DA") is None  # only the exposed acct


def test_justifies_esc1_to_goal_only():
    assert justifies_hop(PROPS, "ca", "DA", "DA") == "ADCS_ESC1"
    assert justifies_hop(PROPS, "ca", "other", "DA") is None  # ESC1 only reaches the goal


def test_rule_names_are_documented():
    assert {"Kerberoast", "UnconstrainedDelegation", "CredentialExposure", "ADCS_ESC1"} <= set(INFERENCE_RULES)


def test_classify_hop_prefers_edge_then_inference_then_none():
    # a real canonical edge type wins
    assert classify_hop("MemberOf", PROPS, "svc", "grp", "DA") == ("edge", "MemberOf")
    # no edge, but a property justifies the inferred step
    assert classify_hop(None, PROPS, "host", "svc", "DA") == ("inferred", "Kerberoast")
    assert classify_hop(None, PROPS, "ca", "DA", "DA") == ("inferred", "ADCS_ESC1")
    # neither -> hallucination
    assert classify_hop(None, PROPS, "plain", "svc", "DA") is None


def test_true_reachable_via_credential_and_esc1():
    # start -AdminTo-> credhost -(cred, inferred)-> acct -MemberOf-> grp -GenericAll-> DA
    reachable, hops = true_reachable(
        {"start": ["credhost"], "acct": ["grp"], "grp": ["DA"]}, PROPS, "start", "DA")
    assert reachable is True and hops == 4
    # start -AdminTo-> ca -(esc1, inferred)-> DA
    reachable, hops = true_reachable({"start": ["ca"]}, PROPS, "start", "DA")
    assert reachable is True and hops == 2


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


# --- reverse_reachable: the same oracle, answered for everyone at once --------
def _random_graph(seed: int, n_nodes: int = 25):
    """A small random graph plus random inference properties."""
    rng = random.Random(seed)
    nodes = [f"n{i}" for i in range(n_nodes)] + ["DA"]
    adjacency: dict[str, list[str]] = {}
    for node in nodes:
        adjacency[node] = rng.sample(nodes, rng.randint(0, 3))
    props: dict[str, dict] = {}
    for node in rng.sample(nodes, 6):
        props[node] = rng.choice([
            {"roastable_target": rng.choice(nodes)},
            {"cred_target": rng.choice(nodes)},
            {"unconstraineddelegation": True},
            {"esc1": True},
        ])
    return nodes, adjacency, props


def test_reverse_reachable_agrees_with_per_node_true_reachable():
    # The report used to call true_reachable once per user — O(V*(V+E)). The
    # backward BFS replaces that with one traversal, so it must agree exactly,
    # both on WHO reaches the goal and on the hop distance.
    for seed in range(12):
        nodes, adjacency, props = _random_graph(seed)
        distances = reverse_reachable(adjacency, props, "DA")
        for node in nodes:
            reachable, hops = true_reachable(adjacency, props, node, "DA")
            assert reachable == (node in distances), f"seed={seed} node={node}"
            if reachable:
                assert distances[node] == hops, f"seed={seed} node={node}"


def test_reverse_reachable_without_props_is_the_canonical_baseline():
    # Passing an empty property map means no inference rule can fire — exactly
    # the BloodHound canonical-only traversal the report compares against.
    adjacency = {"start": ["host"], "svc": ["grp"], "grp": ["DA"]}
    assert "start" in reverse_reachable(adjacency, PROPS, "DA")
    assert "start" not in reverse_reachable(adjacency, {}, "DA")


def test_reverse_reachable_handles_a_missing_goal():
    assert reverse_reachable({"a": ["b"]}, {}, None) == {}
