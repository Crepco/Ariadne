"""Offline tests for report outputs (triage proxy + grounded explanation)."""

from __future__ import annotations

from types import SimpleNamespace

from ariadne import report
from ariadne.inference import justifies_hop


class _Ctx:
    """Minimal ScoringContext stand-in for verify_path/report."""

    def __init__(self, edges, names, props, goal="DA"):
        self._edges = edges
        self.names = names
        self.props = props
        self.goal_oid = goal
        self.oids = set(names)

    def resolve(self, token):
        return token if token in self.oids else None

    def hop_kind(self, a, b):
        t = self._edges.get((a, b))
        if t is not None:
            return ("edge", t)
        rule = justifies_hop(self.props, a, b, self.goal_oid)
        return ("inferred", rule) if rule else None


def test_rank_paths_orders_by_impact():
    ctx = _Ctx(
        edges={},
        names={"u": "U", "dc": "DC", "da": "DA"},
        props={"dc": {"is_dc": True}, "da": {"highvalue": True}, "u": {}},
    )
    ranked = report.rank_paths(ctx, [["u", "da"], ["u", "dc", "da"]])
    # The path touching two high-value nodes (dc + da) ranks above the shorter one.
    assert ranked[0]["path"] == ["U", "DC", "DA"]
    assert ranked[0]["high_value_nodes"] == ["DC", "DA"]


def test_explain_path_narrates_verified_path(monkeypatch):
    monkeypatch.setattr(report, "chat", lambda messages: SimpleNamespace(text="NARRATIVE"))
    ctx = _Ctx(
        edges={("a", "b"): "ForceChangePassword", ("b", "DA"): "GenericAll"},
        names={"a": "A", "b": "B", "DA": "DOMAIN ADMINS"},
        props={},
    )
    out = report.explain_path(ctx, ["a", "b", "DA"])
    assert out == "NARRATIVE"


def test_explain_path_refuses_unverified_path(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(report, "chat", lambda messages: called.__setitem__("n", called["n"] + 1) or SimpleNamespace(text="x"))
    ctx = _Ctx(edges={}, names={"a": "A", "DA": "DOMAIN ADMINS"}, props={})
    out = report.explain_path(ctx, ["a", "DA"])  # no edge a->DA, no inference
    assert "Could not verify" in out
    assert called["n"] == 0  # must NOT call the LLM on an unverified path


def test_domain_report_is_grounded_markdown(monkeypatch):
    from ariadne.checks import Finding

    findings = {
        "adcs_esc1": [Finding("adcs_esc1", "PLANT_E_CA@CORP.LOCAL", "ESC1 on host", "critical",
                              ["PLANT_E_CA: esc1=true"])],
        "kerberoastable_to_da": [Finding("kerberoastable_to_da", "SVC@CORP.LOCAL", "roastable to DA",
                                         "high", ["hasspn=true, crackable=true"])],
        "dangerous_acls": [],
        "unconstrained_delegation": [],
        "credential_exposure": [],
        "nested_da": [],
        "session_exposure": [],
    }
    monkeypatch.setattr(report, "run_all", lambda ctx: findings)

    def fake_run_read(driver, q, **kw):
        if "labels(n)" in q:
            return [{"label": "User", "c": 3}, {"label": "Computer", "c": 2}]
        if "count(r)" in q:
            return [{"c": 42}]
        return [{"oid": "u1"}, {"oid": "u2"}, {"oid": "u3"}]  # the user list
    monkeypatch.setattr(report, "run_read", fake_run_read)

    # u1 reaches DA ONLY with inference (props truthy) — the beats-BloodHound case;
    # u2 reaches canonically too; u3 not at all. The canonical call passes {} (falsy).
    def fake_true(adj, props, oid, goal):
        if oid == "u1":
            return (True, 3) if props else (False, -1)
        if oid == "u2":
            return (True, 2)
        return (False, -1)
    monkeypatch.setattr(report, "true_reachable", fake_true)

    ctx = SimpleNamespace(driver=None, database="neo4j", canonical_adj={}, goal_oid="DA",
                          names={"u1": "PLANT_E@CORP.LOCAL"}, props={"u1": {"esc1": True}})
    md = report.domain_report(ctx)

    assert md.startswith("# Ariadne domain audit — CORP.LOCAL")
    assert "2 total — 1 critical, 1 high" in md            # severity roll-up
    assert "2/3 users can reach DOMAIN ADMINS" in md       # footholds
    assert "adcs esc1 — 1 finding(s)" in md and "critical" in md
    assert "inferred — BloodHound-blind" in md             # inferred checks tagged
    assert "Paths BloodHound can't see" in md
    assert "1 user(s) reach DOMAIN ADMINS ONLY" in md      # only u1 is advanced-only
    assert "## Remediation" in md
