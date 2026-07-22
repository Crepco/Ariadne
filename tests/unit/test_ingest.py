"""Offline tests for BloodHound-export normalisation (no database)."""

from __future__ import annotations

import bloodhound as bh
import export_bloodhound as ex
import generate
from ariadne.inference import true_reachable
from ariadne.schema import CANONICAL_EDGES, INFERENCE_PROPERTIES


def _export():
    # A tiny BloodHound-shaped export: a user with an ACL over Domain Admins,
    # a group with a member, and a computer with unconstrained delegation.
    return {
        "User": [
            {"ObjectIdentifier": "U1", "Properties": {"name": "alice@x", "hasspn": True, "admincount": True}},
            {"ObjectIdentifier": "U2", "Properties": {"name": "bob@x"}},
        ],
        "Group": [
            {"ObjectIdentifier": "G-DA", "Properties": {"name": "DOMAIN ADMINS@x", "highvalue": True},
             "Members": [{"ObjectIdentifier": "U2"}],
             "Aces": [{"PrincipalSID": "U1", "RightName": "GenericAll"}]},
        ],
        "Computer": [
            {"ObjectIdentifier": "C1", "Properties": {"name": "web.x", "unconstraineddelegation": True},
             "LocalAdmins": [{"ObjectIdentifier": "U2"}],
             "Sessions": [{"ObjectIdentifier": "U1"}]},
        ],
    }


def test_nodes_and_props_are_normalised():
    graph = bh.build_graph_from_export(_export())
    by_oid = {n["objectid"]: n for n in graph["nodes"]}
    assert by_oid["U1"]["label"] == "User"
    assert by_oid["U1"]["props"]["hasspn"] is True
    assert by_oid["C1"]["props"]["unconstraineddelegation"] is True
    assert graph["goal"] == "G-DA"           # Domain Admins group detected


def test_edges_are_canonical_only():
    graph = bh.build_graph_from_export(_export())
    types = {e[0] for e in graph["edges"]}
    assert types <= set(CANONICAL_EDGES)
    # GenericAll ACE, group membership, local-admin, and session all mapped:
    assert ("GenericAll", "U1", "G-DA") in graph["edges"]
    assert ("MemberOf", "U2", "G-DA") in graph["edges"]
    assert ("AdminTo", "U2", "C1") in graph["edges"]
    assert ("HasSession", "C1", "U1") in graph["edges"]


def test_crackable_heuristic_and_roastable_target():
    # Default heuristic marks privileged (admincount) SPN accounts crackable, and
    # a host with that account's session exposes it (roastable_target).
    graph = bh.build_graph_from_export(_export(), crackable="spn-admincount")
    by_oid = {n["objectid"]: n for n in graph["nodes"]}
    assert by_oid["U1"]["props"]["crackable"] is True         # hasspn + admincount
    assert by_oid["C1"]["props"]["roastable_target"] == "U1"  # host exposes U1 via session


def test_all_spn_heuristic():
    export = {"User": [{"ObjectIdentifier": "U3", "Properties": {"name": "svc@x", "hasspn": True}}]}
    graph = bh.build_graph_from_export(export, crackable="all-spn")
    assert graph["nodes"][0]["props"]["crackable"] is True


def test_primarygroupsid_becomes_membership():
    # BHCE leans on PrimaryGroupSID for most membership; the ingest must turn it
    # into a MemberOf edge just like an explicit Members entry.
    export = {
        "User": [{"ObjectIdentifier": "U9", "Properties": {"name": "p@x", "primarygroupsid": "G9"}}],
        "Group": [{"ObjectIdentifier": "G9", "Properties": {"name": "GROUP9@x"}, "Members": []}],
    }
    graph = bh.build_graph_from_export(export)
    assert ("MemberOf", "U9", "G9") in graph["edges"]


def test_results_wrapped_principal_lists():
    # BHCE wraps some principal lists as {"Results": [...]} — the ingest unwraps them.
    export = {
        "Computer": [{
            "ObjectIdentifier": "C9", "Properties": {"name": "host.x"},
            "LocalAdmins": {"Results": [{"ObjectIdentifier": "U9"}]},
            "PrivilegedSessions": {"Results": [{"ObjectIdentifier": "U8"}]},
        }],
    }
    graph = bh.build_graph_from_export(export)
    assert ("AdminTo", "U9", "C9") in graph["edges"]
    assert ("HasSession", "C9", "U8") in graph["edges"]


def test_inference_properties_pass_through():
    # A pre-annotated export (e.g. an Ariadne round-trip) keeps its inference props
    # rather than having them re-derived from the heuristic.
    export = {
        "Computer": [{"ObjectIdentifier": "C1", "Properties": {
            "name": "ca.x", "esc1": True, "cred_target": "U2", "roastable_target": "U3"}}],
    }
    graph = bh.build_graph_from_export(export)
    props = graph["nodes"][0]["props"]
    assert props["esc1"] is True
    assert props["cred_target"] == "U2"
    assert props["roastable_target"] == "U3"


def _props_map(graph):
    return {n["objectid"]: {k: n["props"].get(k) for k in INFERENCE_PROPERTIES}
            for n in graph["nodes"]}


def test_roundtrip_preserves_edges_and_reachability():
    # Build a synthetic graph, export it as BloodHound-CE JSON, re-ingest it, and
    # assert the canonical edges and every planted attack path survive intact — the
    # end-to-end proof that the reader pipeline runs on a BloodHound-shaped export.
    graph = generate.build_graph(n_users=40, n_computers=8, n_groups=8, seed=3, plant=True)
    objects = ex.graph_to_objects(graph)
    reingested = bh.build_graph_from_export(objects, crackable="none")

    assert reingested["goal"] == graph["goal"]
    # Canonical edges are identical (order-insensitive).
    assert reingested["edges"] == set(graph["edges"])

    # Every planted chain — including the inference-only ones (kerberoast, ESC1,
    # credential exposure, delegation) — is still truly reachable after the trip.
    canon = _adjacency(reingested)
    props = _props_map(reingested)
    for chain in graph["planted"]:
        reachable, _ = true_reachable(canon, props, chain["start"], reingested["goal"])
        assert reachable, f"chain {chain['name']} lost in round trip"


def _adjacency(graph):
    from collections import defaultdict
    adj = defaultdict(list)
    for etype, src, dst in graph["edges"]:
        adj[src].append(dst)
    return adj
