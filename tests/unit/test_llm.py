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


def test_parse_response_returns_content_and_usage():
    resp = _Resp({
        "choices": [{"message": {"content": "hi"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5, "cost": 0.001},
    })
    content, usage = llm._parse_response(resp)
    assert content == "hi"
    assert usage == {"prompt_tokens": 3, "completion_tokens": 5, "cost": 0.001}


def test_usage_fields_defaults_and_parsing():
    assert llm._usage_fields({}) == (0, 0, 0.0)
    assert llm._usage_fields({"prompt_tokens": 2, "completion_tokens": 4, "cost": 0.5}) == (2, 4, 0.5)


def test_chat_dispatches_and_ask_llm_wraps(monkeypatch):
    monkeypatch.setitem(llm._state, "provider", "openrouter")
    monkeypatch.setattr(llm, "_openrouter", lambda messages, model, mr: llm.LLMResult("ok", 1, 2, 0.003))
    res = llm.chat([{"role": "user", "content": "x"}])
    assert res.text == "ok"
    assert (res.prompt_tokens, res.completion_tokens, res.cost_usd) == (1, 2, 0.003)
    # ask_llm is a single-turn wrapper returning just the text.
    assert llm.ask_llm("x") == "ok"


class _FakeResp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_openrouter_rotates_past_402_to_a_funded_key(monkeypatch):
    # First key is out of credit (402), second succeeds — the run must roll over
    # rather than failing, and it should return the funded key's completion.
    calls = {"n": 0}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResp(402, text="requires more credits")
        return _FakeResp(200, {
            "choices": [{"message": {"content": "done"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "cost": 0.0009},
        })

    monkeypatch.setattr(llm, "_OPENROUTER_KEYS", ["k1", "k2"])
    monkeypatch.setattr(llm, "requests", type("R", (), {"post": staticmethod(fake_post),
                                                        "RequestException": Exception}))
    res = llm._openrouter([{"role": "user", "content": "x"}], "some/model", max_retries=4)
    assert res.text == "done"
    assert calls["n"] == 2  # rotated from the 402 key to the funded one


def test_messages_to_prompt_tags_assistant_turns():
    prompt = llm._messages_to_prompt([
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ])
    assert prompt == "sys\nu1\nAssistant: a1"


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
