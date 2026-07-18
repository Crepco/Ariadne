"""Offline tests for the agent loop's JSON parsing (no LLM, no database)."""

from __future__ import annotations

from ariadne.agent.loop import _as_str_list, _parse_json


def test_plain_object():
    assert _parse_json('{"action": "finish", "path": ["A", "B"]}') == {
        "action": "finish",
        "path": ["A", "B"],
    }


def test_object_wrapped_in_prose_and_fence():
    text = 'Here is my move:\n```json\n{"action": "query_outbound_edges", "input": "x"}\n```\ndone'
    assert _parse_json(text) == {"action": "query_outbound_edges", "input": "x"}


def test_bare_json_string_is_rejected():
    # A JSON string is valid JSON but not an action object; must not be returned
    # (otherwise the caller's action.get(...) raises AttributeError).
    assert _parse_json('"just some text"') is None


def test_bare_json_list_is_rejected():
    assert _parse_json("[1, 2, 3]") is None


def test_bare_number_is_rejected():
    assert _parse_json("42") is None


def test_unparseable_text_returns_none():
    assert _parse_json("no json here at all") is None


def test_as_str_list():
    assert _as_str_list(["A", 1, None]) == ["A", "1", "None"]
    assert _as_str_list("not a list") is None
    assert _as_str_list(None) is None
