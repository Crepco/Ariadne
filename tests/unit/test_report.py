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
