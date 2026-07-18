"""Offline tests for the LLM backend helpers (no network calls)."""

from __future__ import annotations

from ariadne.agent import llm


class _Resp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, data, text=""):
        self._data = data
        self.text = text

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


def test_extract_content_normal():
    resp = _Resp({"choices": [{"message": {"content": "hello"}}]})
    assert llm._extract_content(resp) == "hello"


def test_extract_content_inline_error_body():
    resp = _Resp({"error": {"message": "boom"}})
    assert llm._extract_content(resp) is None


def test_extract_content_empty_choices():
    assert llm._extract_content(_Resp({"choices": []})) is None


def test_extract_content_null_content():
    resp = _Resp({"choices": [{"message": {"content": None}}]})
    assert llm._extract_content(resp) is None


def test_extract_content_non_json_body():
    assert llm._extract_content(_Resp(ValueError("not json"))) is None


def test_load_keys_parses_and_trims(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEYS", " a , b ,, c ")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert llm._load_keys() == ["a", "b", "c"]


def test_set_model_infers_provider_from_slug():
    original_model = llm.active_model()
    original_provider = llm._state["provider"]
    try:
        llm.set_model("anthropic/claude-x")
        assert llm.active_model() == "anthropic/claude-x"
        assert llm._state["provider"] == "openrouter"

        llm.set_model("gemini-3.1-flash-lite")
        assert llm._state["provider"] == "gemini"

        llm.set_model("some-model", provider="openrouter")
        assert llm._state["provider"] == "openrouter"
    finally:
        llm.set_model(original_model, provider=original_provider)
