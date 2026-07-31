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


def test_invalid_finish_triggers_a_revision_then_accepts(monkeypatch):
    # First finish drops a node; verify_path rejects it, the agent gets the reason
    # back, and its corrected second finish is accepted.
    replies = iter([
        LLMResult('{"action":"finish","answer":"A -> DOMAIN ADMINS","path":["A","DOMAIN ADMINS"]}', 1, 1, 0.0),
        LLMResult('{"action":"finish","answer":"A -> SVC -> DOMAIN ADMINS","path":["A","SVC","DOMAIN ADMINS"]}', 1, 1, 0.0),
    ])
    verdicts = iter([
        {"valid": False, "reason": "Hop A -> DOMAIN ADMINS is NOT a real step."},
        {"valid": True, "hops": []},
    ])
    monkeypatch.setattr(loop, "chat", lambda history: next(replies))
    monkeypatch.setattr(loop, "TOOLS", {"verify_path": lambda path: next(verdicts)})

    res = loop.run_agent("A", max_steps=5, verbose=False)

    assert res.finished is True
    assert res.path_field == ["A", "SVC", "DOMAIN ADMINS"]   # the repaired path
    assert res.steps == 2                                    # took a revision turn


def test_verify_rejection_budget_is_bounded(monkeypatch):
    # verify_path always rejects; after max_revisions the finish is accepted anyway
    # (the loop must not spin forever on a stubborn model).
    monkeypatch.setattr(
        loop, "chat",
        lambda history: LLMResult('{"action":"finish","answer":"A -> DOMAIN ADMINS","path":["A","DOMAIN ADMINS"]}', 1, 1, 0.0),
    )
    monkeypatch.setattr(loop, "TOOLS", {"verify_path": lambda path: {"valid": False, "reason": "nope"}})

    res = loop.run_agent("A", max_steps=10, verbose=False, max_revisions=2)

    assert res.finished is True
    assert res.steps == 3   # 2 rejected revisions + the accepted-anyway finish


def test_no_path_finish_skips_verification(monkeypatch):
    # A NO-PATH finish must never be sent to verify_path (there is nothing to verify).
    calls = {"verify": 0}

    def _verify(path):
        calls["verify"] += 1
        return {"valid": False, "reason": "should not be called"}

    monkeypatch.setattr(
        loop, "chat",
        lambda history: LLMResult('{"action":"finish","answer":"NO PATH FOUND","path":[]}', 1, 1, 0.0),
    )
    monkeypatch.setattr(loop, "TOOLS", {"verify_path": _verify})

    res = loop.run_agent("A", max_steps=5, verbose=False)

    assert res.finished is True
    assert res.path_field == []
    assert calls["verify"] == 0


def test_dict_input_is_spread_over_a_multi_argument_tool(monkeypatch):
    # Regression guard: the dispatcher used to pass a single positional argument
    # to every tool, so check_path_exists (which needs two) raised TypeError on
    # every call and was silently dead while still advertised in the prompt.
    seen = {}

    def check_path_exists(start_objectid, goal_objectid, database=None):
        seen.update(start=start_objectid, goal=goal_objectid)
        return {"exists": True}

    replies = iter([
        LLMResult('{"action":"check_path_exists",'
                  '"input":{"start_objectid":"S-1","goal_objectid":"S-2"}}', 1, 1, 0.0),
        LLMResult('{"action":"finish","answer":"NO PATH FOUND","path":[]}', 1, 1, 0.0),
    ])
    monkeypatch.setattr(loop, "chat", lambda history: next(replies))
    monkeypatch.setattr(loop, "TOOLS", {"check_path_exists": check_path_exists})

    res = loop.run_agent("A", max_steps=5, verbose=False)

    assert seen == {"start": "S-1", "goal": "S-2"}
    assert res.tool_calls == 1


def test_multi_argument_tool_called_with_a_bare_string_explains_itself(monkeypatch):
    # The observation has to teach the model the right shape, otherwise it just
    # abandons the tool after one opaque failure.
    observations = []

    def check_path_exists(start_objectid, goal_objectid, database=None):
        return {"exists": True}

    replies = iter([
        LLMResult('{"action":"check_path_exists","input":"S-1"}', 1, 1, 0.0),
        LLMResult('{"action":"finish","answer":"NO PATH FOUND","path":[]}', 1, 1, 0.0),
    ])
    monkeypatch.setattr(loop, "chat", lambda history: next(replies))
    monkeypatch.setattr(loop, "TOOLS", {"check_path_exists": check_path_exists})

    loop.run_agent("A", max_steps=5, verbose=False,
                   on_step=lambda s: observations.append(s.get("observation")))

    message = str(observations[0])
    assert "start_objectid" in message and "goal_objectid" in message
    assert '"input"' in message           # shows the object form to use


def test_single_argument_tools_still_take_a_bare_value(monkeypatch):
    replies = iter([
        LLMResult('{"action":"search_node","input":"USER0001"}', 1, 1, 0.0),
        LLMResult('{"action":"finish","answer":"NO PATH FOUND","path":[]}', 1, 1, 0.0),
    ])
    monkeypatch.setattr(loop, "chat", lambda history: next(replies))
    monkeypatch.setattr(loop, "TOOLS", {"search_node": lambda name, database=None: [name]})

    res = loop.run_agent("A", max_steps=5, verbose=False)
    assert res.tool_calls == 1


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

    res = loop.run_agent("A", max_steps=5, verbose=False, max_reformats=0)

    assert res.finished is False
    assert res.answer == "I give up, sorry."
    assert res.tool_calls == 0


def test_prose_answer_is_re_asked_as_json_instead_of_ending_the_run(monkeypatch):
    # Observed on a real run: the model traced and verified the correct path,
    # then wrote it as prose on the final turn. Ending there scored a solved
    # task as "ran out of steps" — so an unparseable reply is re-asked first.
    replies = iter([
        LLMResult("A -> B -> DOMAIN ADMINS", 1, 1, 0.0),                       # prose
        LLMResult('{"action":"finish","answer":"A -> B -> DOMAIN ADMINS",'
                  '"path":["A","B","DOMAIN ADMINS"]}', 1, 1, 0.0),             # corrected
    ])
    monkeypatch.setattr(loop, "chat", lambda history: next(replies))
    monkeypatch.setattr(loop, "TOOLS", {"verify_path": lambda path: {"valid": True}})

    res = loop.run_agent("A", max_steps=5, verbose=False)

    assert res.finished is True
    assert res.path_field == ["A", "B", "DOMAIN ADMINS"]


def test_reformat_budget_is_bounded(monkeypatch):
    # A model that never returns JSON must not consume the whole step budget.
    monkeypatch.setattr(loop, "chat", lambda history: LLMResult("still prose", 1, 1, 0.0))

    res = loop.run_agent("A", max_steps=10, verbose=False, max_reformats=2)

    assert res.finished is False
    assert res.steps == 3          # 2 reformat attempts + the give-up turn
    assert res.answer == "still prose"
