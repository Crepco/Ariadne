"""Offline tests for the ReAct loop mechanics (LLM and tools are faked)."""

from __future__ import annotations

from ariadne.agent import loop
from ariadne.agent.llm import LLMResult
from ariadne.agent.prompts import SYSTEM_PROMPT


def test_prompt_leads_with_search_node_and_has_no_copyable_fake_oid():
    # Regression guard: a prior prompt let the model copy a placeholder object id
    # (`"input": "S-1-5-21-...-900001"`) and skip search_node, so every run gave
    # up after 2 dead-end calls. The first example action must be search_node,
    # and no example may hand the model a fake object id to paste verbatim.
    pre = loop._user_preamble("PLANT_A_START", 20)
    assert '"action": "search_node"' in pre
    assert pre.index('"action": "search_node"') < pre.index('"action": "query_outbound_edges"')
    assert '"input": "S-1-5-21-' not in pre
    assert '"input": "S-1-5-21-' not in SYSTEM_PROMPT


def test_run_agent_finishes_and_accumulates_usage(monkeypatch):
    replies = iter([
        LLMResult('{"action":"query_outbound_edges","input":"OID"}', 10, 2, 0.001),
        LLMResult('{"action":"finish","answer":"A -> DOMAIN ADMINS","path":["A","DOMAIN ADMINS"]}', 8, 3, 0.002),
    ])
    monkeypatch.setattr(loop, "chat", lambda history: next(replies))
    monkeypatch.setattr(loop, "TOOLS", {"query_outbound_edges": lambda arg: "some observation"})

    res = loop.run_agent("A", max_steps=5, verbose=False)

    assert res.finished is True
    assert res.path_field == ["A", "DOMAIN ADMINS"]
    assert res.tool_calls == 1
    assert res.steps == 2
    assert res.max_steps == 5
    assert res.prompt_tokens == 18
    assert res.completion_tokens == 5
    assert abs(res.cost_usd - 0.003) < 1e-9


def test_run_agent_reports_unknown_tool_without_counting_a_call(monkeypatch):
    replies = iter([
        LLMResult('{"action":"bogus_tool","input":"x"}', 1, 1, 0.0),
        LLMResult('{"action":"finish","answer":"NO PATH FOUND","path":[]}', 1, 1, 0.0),
    ])
    monkeypatch.setattr(loop, "chat", lambda history: next(replies))

    res = loop.run_agent("A", max_steps=5, verbose=False)

    assert res.finished is True
    assert res.tool_calls == 0


def test_run_agent_hits_max_steps(monkeypatch):
    monkeypatch.setattr(
        loop, "chat",
        lambda history: LLMResult('{"action":"query_inbound_edges","input":"x"}', 1, 1, 0.0),
    )
    monkeypatch.setattr(loop, "TOOLS", {"query_inbound_edges": lambda arg: "obs"})

    res = loop.run_agent("A", max_steps=3, verbose=False)

    assert res.finished is False
    assert res.steps == 3
    assert res.answer == "Maximum reasoning steps exceeded."


def test_run_agent_non_json_reply_ends_run(monkeypatch):
    monkeypatch.setattr(loop, "chat", lambda history: LLMResult("I give up, sorry.", 1, 1, 0.0))

    res = loop.run_agent("A", max_steps=5, verbose=False)

    assert res.finished is False
    assert res.answer == "I give up, sorry."
    assert res.tool_calls == 0
