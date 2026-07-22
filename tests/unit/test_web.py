"""Offline tests for the web layer's pure helpers and the loop's on_step hook."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("flask")  # web extra not always installed

from ariadne.web import app as webapp  # noqa: E402
from ariadne.agent import loop  # noqa: E402
from ariadne.agent.llm import LLMResult  # noqa: E402


def test_primary_label_prefers_specific_label():
    assert webapp._primary_label(["Base", "User"]) == "User"
    assert webapp._primary_label(["Group"]) == "Group"
    assert webapp._primary_label([]) == "Base"


def test_discovered_oids_collects_inputs_and_observation_targets():
    steps = [
        {"action": "search_node", "input": "PLANT_A_START",
         "observation": [{"objectid": "S-1-5-21-1"}]},
        {"action": "query_outbound_edges", "input": "S-1-5-21-1",
         "observation": [{"objectid": "S-1-5-21-2"}, {"objectid": "S-1-5-21-3"}]},
        {"action": "get_node_properties", "input": "S-1-5-21-2",
         "observation": {"objectid": "S-1-5-21-2", "roastable_target": "S-1-5-21-9"}},
    ]
    oids = webapp._discovered_oids(steps, ["S-1-5-21-7"])
    assert {"S-1-5-21-1", "S-1-5-21-2", "S-1-5-21-3", "S-1-5-21-7"} <= oids


def test_observation_summary_flags_inferred_step():
    s = {"action": "get_node_properties", "observation": {"unconstraineddelegation": True}}
    assert "inferred step available" in webapp._observation_summary(s)
    assert webapp._observation_summary({"action": "search_node", "observation": [1, 2]}) == "resolved 2 node(s)"


def _fake_ctx():
    return SimpleNamespace(names={}, name_to_oid={}, props={}, driver=None, database="neo4j")


def test_api_chat_routes_to_grounded_text_executor(monkeypatch):
    import ariadne.chat as chatmod
    monkeypatch.setattr(webapp.ScoringContext, "load", classmethod(lambda cls: _fake_ctx()))
    monkeypatch.setattr(chatmod, "route", lambda q: {"intent": "help", "args": {}})
    r = webapp.app.test_client().post("/api/chat", json={"message": "what can you do?"})
    body = r.get_json()
    assert r.status_code == 200
    assert "graph" in body["answer"].lower()  # help text is grounded, mentions the graph


def test_api_chat_refuses_write_cypher(monkeypatch):
    import ariadne.chat as chatmod
    monkeypatch.setattr(webapp.ScoringContext, "load", classmethod(lambda cls: _fake_ctx()))
    monkeypatch.setattr(chatmod, "route",
                        lambda q: {"intent": "cypher", "args": {"query": "MATCH (n) DETACH DELETE n"}})
    body = webapp.app.test_client().post("/api/chat", json={"message": "delete everything"}).get_json()
    assert "Refused" in body["answer"]  # safety invariant holds through the web layer


def test_api_chat_requires_a_message():
    assert webapp.app.test_client().post("/api/chat", json={"message": "  "}).status_code == 400


def test_api_report_returns_markdown(monkeypatch):
    monkeypatch.setattr(webapp.ScoringContext, "load", classmethod(lambda cls: _fake_ctx()))
    monkeypatch.setattr(webapp, "domain_report", lambda ctx: "# Ariadne domain audit — X\n")
    r = webapp.app.test_client().get("/api/report")
    body = r.get_json()
    assert r.status_code == 200
    assert body["markdown"].startswith("# Ariadne domain audit")


def test_run_agent_on_step_receives_structured_events(monkeypatch):
    replies = iter([
        LLMResult('{"action":"query_outbound_edges","input":"OID"}', 1, 1, 0.0),
        LLMResult('{"action":"finish","answer":"A -> DOMAIN ADMINS","path":["A","DOMAIN ADMINS"]}', 1, 1, 0.0),
    ])
    monkeypatch.setattr(loop, "chat", lambda history: next(replies))
    monkeypatch.setattr(loop, "TOOLS", {"query_outbound_edges": lambda arg: [{"objectid": "X"}]})
    events = []
    loop.run_agent("A", max_steps=5, verbose=False, on_step=events.append)
    assert [e["action"] for e in events] == ["query_outbound_edges", "finish"]
    assert events[0]["observation"] == [{"objectid": "X"}]
