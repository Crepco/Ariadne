"""Offline tests for the grounded chat assistant (router + safety invariant)."""

from __future__ import annotations

from types import SimpleNamespace

from ariadne import chat
from ariadne.inference import justifies_hop


class _Ctx:
    def __init__(self, edges=None, names=None, props=None, adj=None, goal="DA"):
        self._edges = edges or {}
        self.names = names or {}
        self.props = props or {}
        self.canonical_adj = adj or {}
        self.name_to_oid = {v.upper(): k for k, v in self.names.items()}
        self.goal_oid = goal
        self.oids = set(self.names)
        self.driver = None
        self.database = "neo4j"

    def resolve(self, token):
        return token if token in self.oids else None

    def hop_kind(self, a, b):
        t = self._edges.get((a, b))
        if t is not None:
            return ("edge", t)
        rule = justifies_hop(self.props, a, b, self.goal_oid)
        return ("inferred", rule) if rule else None


# --- pure helpers ----------------------------------------------------------
def test_is_read_only():
    assert chat.is_read_only("MATCH (n) RETURN n LIMIT 5") is True
    assert chat.is_read_only("match (n) detach delete n") is False
    assert chat.is_read_only("MATCH (n) SET n.x = 1 RETURN n") is False
    assert chat.is_read_only("MERGE (n:X) RETURN n") is False


def test_parse_intent_variants():
    assert chat.parse_intent('{"intent":"check","args":{"name":"nested_da"}}') == {
        "intent": "check", "args": {"name": "nested_da"}}
    assert chat.parse_intent("prose {\"intent\":\"help\"} more") == {"intent": "help", "args": {}}
    assert chat.parse_intent("no json here") == {"intent": "help", "args": {}}


# --- safety invariant + dispatch ------------------------------------------
def test_cypher_write_is_refused(monkeypatch):
    monkeypatch.setattr(chat, "route", lambda q: {"intent": "cypher", "args": {"query": "MATCH (n) DELETE n"}})
    out = chat.handle("delete everything", _Ctx(), {})
    assert "Refused" in out


def test_find_path_rejects_unverified_path(monkeypatch):
    # The router asks to find a path; the agent proposes a bogus one; the verifier
    # rejects it, so the assistant must NOT present it (the safety invariant).
    monkeypatch.setattr(chat, "route", lambda q: {"intent": "find_path", "args": {"start": "A"}})
    fake_result = SimpleNamespace(answer="A -> DOMAIN ADMINS", path_field=["A", "DOMAIN ADMINS"])
    import ariadne.agent.loop as loop
    monkeypatch.setattr(loop, "run_agent", lambda start, verbose=False: fake_result)
    ctx = _Ctx(edges={}, names={"A": "A", "DA": "DOMAIN ADMINS"})  # no real A->DA edge
    out = chat.handle("path from A", ctx, {})
    assert "No VERIFIED path" in out


def test_check_intent_runs_grounded_check(monkeypatch):
    monkeypatch.setattr(chat, "route", lambda q: {"intent": "check", "args": {"name": "unconstrained_delegation"}})
    ctx = _Ctx(props={"web": {"unconstraineddelegation": True, "is_dc": False}}, names={"web": "WEB"})
    state: dict = {}
    out = chat.handle("any delegation issues?", ctx, state)
    assert "unconstrained_delegation" in out and "WEB" in out
    assert state["last_findings"]  # stored for follow-up drill-down


def test_help_is_default_for_unknown_intent(monkeypatch):
    monkeypatch.setattr(chat, "route", lambda q: {"intent": "banana", "args": {}})
    out = chat.handle("hi", _Ctx(), {})
    assert "answer from the graph" in out
