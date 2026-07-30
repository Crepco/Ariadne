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
    monkeypatch.setattr(llm._client, "provider", "openrouter")
    monkeypatch.setattr(llm, "_openrouter",
                        lambda messages, model, mr, temp=None, mt=None: llm.LLMResult("ok", 1, 2, 0.003))
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


def test_set_temperature_flows_into_the_openrouter_payload(monkeypatch):
    original = llm.active_temperature()
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["temperature"] = json["temperature"]
        return _FakeResp(200, {"choices": [{"message": {"content": "ok"}}], "usage": {}})

    monkeypatch.setattr(llm, "_OPENROUTER_KEYS", ["k1"])
    monkeypatch.setattr(llm, "requests", type("R", (), {"post": staticmethod(fake_post),
                                                        "RequestException": Exception}))
    try:
        llm.set_temperature(0.7)
        assert llm.active_temperature() == 0.7
        llm._openrouter([{"role": "user", "content": "x"}], "some/model", max_retries=1)
        assert captured["temperature"] == 0.7   # the configured value reached the request
    finally:
        llm.set_temperature(original)


def test_set_model_infers_provider_from_slug():
    original_model = llm.active_model()
    original_provider = llm._client.provider
    try:
        llm.set_model("anthropic/claude-x")
        assert llm.active_model() == "anthropic/claude-x"
        assert llm._client.provider == "openrouter"

        llm.set_model("gemini-3.1-flash-lite")
        assert llm._client.provider == "gemini"

        llm.set_model("some-model", provider="openrouter")
        assert llm._client.provider == "openrouter"
    finally:
        llm.set_model(original_model, provider=original_provider)


def test_independent_clients_do_not_share_configuration():
    # The point of LLMClient: a benchmark can hold two models at once without
    # one set_model call clobbering the other's configuration.
    a = llm.LLMClient(model="openai/gpt-4o-mini", temperature=0.0)
    b = llm.LLMClient(model="anthropic/claude-x", temperature=0.7)
    assert (a.provider, b.provider) == ("openrouter", "openrouter")
    assert (a.model, a.temperature) == ("openai/gpt-4o-mini", 0.0)
    assert (b.model, b.temperature) == ("anthropic/claude-x", 0.7)
    assert llm.LLMClient(model="gemini-3.1-flash-lite").provider == "gemini"


def test_split_system_keeps_the_system_prompt_out_of_the_turns():
    # Gemini takes the system prompt in its own slot; folding it into the
    # conversation made that backend run a different prompt from OpenRouter's.
    system, turns = llm._split_system([
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ])
    assert system == "SYS"
    assert "SYS" not in turns
    assert turns == "hello\nAssistant: hi"
