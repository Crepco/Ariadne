"""Offline tests for the property-based vulnerability checks (no database).

Only the checks that read properties/inference are exercised here; the
Cypher-backed checks (dangerous_acls, nested_da, session_exposure) need a live
graph and are covered by the live smoke run.
"""

from __future__ import annotations

from types import SimpleNamespace

from ariadne import checks


def _ctx(props, names, canonical_adj, goal="DA"):
    return SimpleNamespace(props=props, names=names, canonical_adj=canonical_adj, goal_oid=goal)


def test_kerberoastable_to_da_flags_crackable_account_reaching_da():
    props = {
        "host": {"roastable_target": "svc"},
        "svc": {"hasspn": True, "crackable": True},
        "grp": {},
    }
    names = {"svc": "SVC@X", "host": "HOST.X"}
    # svc -MemberOf-> grp -GenericAll-> DA (canonical); reachable via roast from host,
    # but kerberoastable_to_da checks the account's OWN reachability to DA.
    adj = {"svc": ["grp"], "grp": ["DA"]}
    findings = checks.kerberoastable_to_da(_ctx(props, names, adj))
    assert len(findings) == 1
    assert findings[0].subject == "SVC@X"
    assert findings[0].severity == "high"


def test_kerberoastable_ignores_uncrackable_or_unreachable():
    props = {
        "strong": {"hasspn": True, "crackable": False},   # not crackable
        "island": {"hasspn": True, "crackable": True},     # crackable but no path to DA
    }
    findings = checks.kerberoastable_to_da(_ctx(props, {}, {}))
    assert findings == []


def test_unconstrained_delegation_flags_non_dc_hosts_only():
    props = {
        "web": {"unconstraineddelegation": True, "is_dc": False},
        "dc": {"unconstraineddelegation": True, "is_dc": True},   # DCs are expected
        "plain": {"unconstraineddelegation": False},
    }
    names = {"web": "WEB.X", "dc": "DC.X"}
    findings = checks.unconstrained_delegation(_ctx(props, names, {}))
    assert [f.subject for f in findings] == ["WEB.X"]
    assert findings[0].severity == "critical"


def test_checks_registry_and_run_check():
    assert "kerberoastable_to_da" in checks.CHECKS
    props = {"web": {"unconstraineddelegation": True, "is_dc": False}}
    findings = checks.run_check("unconstrained_delegation", _ctx(props, {"web": "WEB"}, {}))
    assert len(findings) == 1


def test_run_check_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        checks.run_check("does_not_exist", _ctx({}, {}, {}))
