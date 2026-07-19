"""Offline tests for BloodHound-export normalisation (no database)."""

from __future__ import annotations

import bloodhound as bh
from ariadne.schema import CANONICAL_EDGES


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
