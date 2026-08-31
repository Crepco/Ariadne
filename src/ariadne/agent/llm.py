"""LLM access for the agent.

Two backends:

* **OpenRouter** (default when ``OPENROUTER_API_KEYS`` is set) — an OpenAI-compatible
  endpoint that fronts many models. Keys are rotated round-robin to spread rate
  limits; the model is configurable via ``OPENROUTER_MODEL`` or ``set_model()``.
* **Gemini** (native free tier) — throttled to stay under 15 requests/min.

The configuration a call needs (provider, model, temperature) lives in an
:class:`LLMClient`. There is a module-level default one, and ``chat`` /
``ask_llm`` / ``set_model`` / ``set_temperature`` operate on it, so the simple
call sites are unchanged. Code that needs two configurations at once — a
benchmark comparing models, say — constructs its own clients instead of mutating
global state, which is what makes a concurrent sweep possible.

``chat(messages)`` is the primary entry point: it takes role-tagged messages
(``system`` / ``user`` / ``assistant``) and returns an :class:`LLMResult` carrying
the completion text plus token/cost usage. ``ask_llm(prompt)`` is a thin
single-turn wrapper that returns just the text.
"""

from __future__ import annotations

import os
import random
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

load_dotenv()


class LLMError(RuntimeError):
    """Raised when the model can't be reached after exhausting retries."""


@dataclass
class LLMResult:
    """A single completion plus its usage accounting."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


Message = dict  # {"role": "system"|"user"|"assistant", "content": str}


# --------------------------------------------------------------------------
# Provider / key configuration
# --------------------------------------------------------------------------
def _load_keys() -> list[str]:
    """API keys from the environment, ignoring unfilled placeholders.

    ``.env.example`` ships ``OPENROUTER_API_KEYS=sk-or-...`` as a template. Left
    as-is it is a non-empty string, so a naive check treats it as a configured
    key and routes every request to OpenRouter — where it 401s — even when the
    user has filled in a different backend's key instead.
    """
    raw = os.getenv("OPENROUTER_API_KEYS") or os.getenv("OPENROUTER_API_KEY") or ""
    return [k.strip() for k in raw.split(",")
            if k.strip() and not k.strip().endswith("...")]


_OPENROUTER_KEYS = _load_keys()
_key_lock = threading.Lock()
_key_position = 0

GEMINI_MODEL = "gemini-3.1-flash-lite"
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
_OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "512"))

# The "OpenRouter" backend is really "any OpenAI-compatible gateway that fronts
# many models behind one bill" — OpenRouter is just the default. Swapping to a
# different gateway (Portkey, a self-hosted proxy to Bedrock/Vertex, ...) is a
# same-shape /chat/completions POST, so it only needs the URL and auth style to
# change, not new request-building code.
#
# GATEWAY_AUTH_STYLE=bearer (default): Authorization: Bearer <key> — OpenRouter,
#   Together, Fireworks, most OpenAI-compatible gateways.
# GATEWAY_AUTH_STYLE=portkey: x-portkey-api-key: <key>, plus an optional
#   x-portkey-virtual-key header from PORTKEY_VIRTUAL_KEY (Portkey routes a
#   request to a specific provider+key pair via that virtual key rather than a
#   plain Bearer token).
_OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
_GATEWAY_AUTH_STYLE = os.getenv("GATEWAY_AUTH_STYLE", "bearer").strip().lower()
_PORTKEY_VIRTUAL_KEY = os.getenv("PORTKEY_VIRTUAL_KEY", "").strip()


def _gateway_headers(key: str) -> dict[str, str]:
    if _GATEWAY_AUTH_STYLE == "portkey":
        headers = {"x-portkey-api-key": key, "Content-Type": "application/json"}
        if _PORTKEY_VIRTUAL_KEY:
            headers["x-portkey-virtual-key"] = _PORTKEY_VIRTUAL_KEY
        return headers
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Title": "Ariadne",
    }

# --- Anthropic (native) ----------------------------------------------------
DEFAULT_ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")
# Thinking counts against max_tokens on this API, and current Claude models
# think by default — the 512-token budget that suits OpenRouter here would
# truncate the answer before the agent's JSON was ever emitted.
_ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "8000"))
# How hard the model works per turn: low | medium | high | xhigh | max.
# Tracing one hop of a graph is not a frontier reasoning problem, and the agent
# runs many turns, so the cheap end is the right default.
ANTHROPIC_EFFORT = os.getenv("ANTHROPIC_EFFORT", "medium")

# USD per million tokens (input, output), for the cost column in the results
# table — the Anthropic API reports token counts but not a price, unlike
# OpenRouter. Prices as of 2026-07; unknown models record tokens with cost 0.0
# rather than guessing.
ANTHROPIC_PRICES = {
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-fable-5": (10.0, 50.0),
}

# USD per million tokens (input, output) for models called directly against a
# gateway (OpenAI's own API here) that doesn't echo a cost field the way
# OpenRouter does — so cost is computed from a known price table instead of
# left at 0.0. Only consulted when the gateway response has no usable cost.
# Prices as of 2026-08; unknown models record tokens with cost 0.0.
GATEWAY_MODEL_PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-5": (1.25, 10.00),   # confirmed from developers.openai.com/api/docs/pricing, 2026-08-31
}

# Models that reject `temperature` outright (HTTP 400) rather than ignoring it.
# Sampling parameters were removed across the current Claude generation; sending
# one is an error, not a no-op, so the temperature sweep has to know to skip it.
_NO_SAMPLING_PARAMS = (
    "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7",
    "claude-sonnet-5", "claude-fable-5", "claude-mythos-5",
)


def accepts_temperature(model: str) -> bool:
    """Whether ``model`` accepts a sampling temperature.

    Matters for ``run_benchmark.py --temperature``: on a model that rejects it,
    every request would 400, so the sweep silently produces zero scored runs
    instead of the variance it was asking for.
    """
    return not any(model.startswith(m) for m in _NO_SAMPLING_PARAMS)


def accepts_effort(model: str) -> bool:
    """Whether ``model`` accepts the ``output_config.effort`` reasoning-depth dial.

    Only the extended-thinking-capable models in ``_NO_SAMPLING_PARAMS`` support
    it (the same models that reject a sampling temperature — effort is what
    replaced it) — non-reasoning models like claude-haiku-4-5 400 on it.
    """
    return any(model.startswith(m) for m in _NO_SAMPLING_PARAMS)


# OpenAI's own reasoning-tier models (o1/o3/o4, gpt-5.x) use a different
# completion-budget param name and reject a non-default temperature — a
# documented, stable API convention (unlike Anthropic's per-model quirks
# above), so a static prefix check is appropriate rather than runtime
# learning. Confirmed directly against api.openai.com, 2026-08-31.
_OPENAI_REASONING_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def _is_openai_reasoning_model(model: str) -> bool:
    return any(model.startswith(p) for p in _OPENAI_REASONING_PREFIXES)


# Reasoning tokens count against the same completion budget as visible output
# on this API — identical to the Claude "thinking counts against max_tokens"
# issue this file already works around with _ANTHROPIC_MAX_TOKENS. The
# OpenRouter-tuned default (2000) let gpt-5 burn its whole budget on internal
# reasoning and emit no visible JSON action text at all (confirmed: 7952
# completion tokens over 5 turns, empty final answer).
_OPENAI_REASONING_MAX_TOKENS = int(os.getenv("OPENAI_REASONING_MAX_TOKENS", "6000"))


def _env_temperature() -> float:
    """Sampling temperature from the environment (default 0 = deterministic)."""
    try:
        return float(os.getenv("OPENROUTER_TEMPERATURE", "0"))
    except ValueError:
        return 0.0


def _next_key() -> str:
    """The next API key, round-robin.

    Reads ``_OPENROUTER_KEYS`` on every call rather than closing over an
    ``itertools.cycle`` built at import time — the cycle version froze whatever
    the environment held when the module first loaded, so tests (and any runtime
    key reload) could set the key list and still get the stale iterator.
    """
    global _key_position
    with _key_lock:
        if not _OPENROUTER_KEYS:
            raise LLMError("No OPENROUTER_API_KEYS configured in .env")
        key = _OPENROUTER_KEYS[_key_position % len(_OPENROUTER_KEYS)]
        _key_position += 1
        return key


def _split_system_blocks(messages: list[Message]) -> tuple[str, list[Message]]:
    """Split role-tagged messages into ``(system_text, conversation_turns)``.

    The Anthropic Messages API takes the system prompt as its own top-level
    parameter, and ``messages`` must contain only user/assistant turns starting
    with a user turn. Ariadne's history is already system-then-alternating, so
    this is a split rather than a rewrite — but the leading-user rule is
    enforced, because a stray assistant-first history is a 400.
    """
    system = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
    turns = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages if m.get("role") in ("user", "assistant")
    ]
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    return system, turns


def _backoff(attempt: int) -> float:
    """Seconds to wait before retry ``attempt``: exponential, jittered, capped.

    Jitter matters once more than one run is in flight — without it, several
    workers rate-limited at the same moment retry in lockstep and get limited
    again together.
    """
    base = min(20.0, 2.0 * (2 ** attempt))
    return base * (0.5 + random.random() / 2)


def _infer_provider(model: str) -> str:
    """Guess the backend from the model id.

    ``claude-…`` is the native Anthropic API; ``vendor/model`` is an OpenRouter
    slug (including ``anthropic/claude-…``, which routes through OpenRouter
    rather than Anthropic directly); anything else is Gemini.
    """
    if model.startswith("claude-"):
        return "anthropic"
    return "openrouter" if "/" in model else "gemini"


# --------------------------------------------------------------------------
# The client
# --------------------------------------------------------------------------
@dataclass
class LLMClient:
    """One model configuration. Construct your own instead of mutating the default
    when you need two live at once (e.g. a multi-model benchmark)."""

    model: str = DEFAULT_OPENROUTER_MODEL
    provider: str | None = None          # inferred from the model slug if omitted
    temperature: float = field(default_factory=_env_temperature)
    max_tokens: int = _OPENROUTER_MAX_TOKENS

    def __post_init__(self) -> None:
        if self.provider is None:
            self.provider = _infer_provider(self.model)

    @property
    def max_retries(self) -> int:
        # A little above the number of rotated keys, so one call can try each
        # funded key once (402/rate-limit retries rotate the key each attempt).
        return max(6, len(_OPENROUTER_KEYS) + 1)

    def chat(self, messages: list[Message], *, max_retries: int | None = None) -> LLMResult:
        retries = self.max_retries if max_retries is None else max_retries
        if self.provider == "anthropic":
            return _anthropic(messages, self.model, retries, self.temperature,
                              self.max_tokens or _ANTHROPIC_MAX_TOKENS)
        if self.provider == "openrouter":
            return _openrouter(messages, self.model, retries, self.temperature, self.max_tokens)
        return _gemini(messages, self.model, retries, self.temperature)


def _default_provider() -> str:
    """Pick a backend from whichever credentials are actually present."""
    if os.getenv("LLM_PROVIDER"):
        return os.environ["LLM_PROVIDER"]
    if _OPENROUTER_KEYS:
        return "openrouter"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "gemini"


_DEFAULT_MODELS = {
    "openrouter": DEFAULT_OPENROUTER_MODEL,
    "anthropic": DEFAULT_ANTHROPIC_MODEL,
    "gemini": GEMINI_MODEL,
}


def _default_client() -> LLMClient:
    provider = _default_provider()
    model = _DEFAULT_MODELS.get(provider, GEMINI_MODEL)
    max_tokens = _ANTHROPIC_MAX_TOKENS if provider == "anthropic" else _OPENROUTER_MAX_TOKENS
    return LLMClient(model=model, provider=provider, max_tokens=max_tokens)


_client = _default_client()

# Back-compat snapshot; prefer active_model() for the live value.
MODEL_NAME = _client.model


def active_model() -> str:
    return _client.model


def set_model(model: str, provider: str | None = None) -> None:
    """Switch the model chat/ask_llm uses. Infers the provider from the slug shape
    (``vendor/model`` -> OpenRouter) unless one is given explicitly."""
    global MODEL_NAME
    _client.model = model
    _client.provider = provider or _infer_provider(model)
    MODEL_NAME = model


def active_temperature() -> float:
    return _client.temperature


def set_temperature(temperature: float) -> None:
    """Set the sampling temperature. 0 is deterministic; raise it (e.g. 0.7) so
    repeated ``--trials`` produce real variance for a variance/CI benchmark."""
    _client.temperature = float(temperature)


# --------------------------------------------------------------------------
# OpenRouter backend
# --------------------------------------------------------------------------
def _parse_response(resp) -> tuple[str | None, dict]:
    """Return ``(content, usage)`` from a 200 response.

    ``content`` is None if the body is malformed — OpenRouter occasionally
    returns HTTP 200 with an inline ``{"error": ...}`` or an empty ``choices``
    list; guard every access so those become a retry, not an unhandled
    ``KeyError``/``IndexError``. ``usage`` is the (possibly empty) usage dict.
    """
    try:
        data = resp.json()
    except ValueError:
        return None, {}
    if not isinstance(data, dict):
        return None, {}
    content = None
    choices = data.get("choices")
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            content = message["content"]
    usage = data.get("usage")
    return content, (usage if isinstance(usage, dict) else {})


def _extract_content(resp) -> str | None:
    """Completion text from a 200 response, or None if malformed (see _parse_response)."""
    return _parse_response(resp)[0]


def _usage_fields(usage: dict, model: str = "") -> tuple[int, int, float]:
    pt = int(usage.get("prompt_tokens") or 0)
    ct = int(usage.get("completion_tokens") or 0)
    cost = float(usage.get("cost") or 0.0)   # OpenRouter reports cost in USD
    if cost == 0.0 and model in GATEWAY_MODEL_PRICES:
        in_price, out_price = GATEWAY_MODEL_PRICES[model]
        cost = (pt * in_price + ct * out_price) / 1_000_000
    return pt, ct, cost


def _openrouter(messages: list[Message], model: str, max_retries: int,
                temperature: float | None = None, max_tokens: int | None = None) -> LLMResult:
    if not _OPENROUTER_KEYS:
        raise LLMError("No OPENROUTER_API_KEYS configured in .env")
    temperature = _client.temperature if temperature is None else temperature
    if max_tokens is None:
        max_tokens = (_OPENAI_REASONING_MAX_TOKENS if _is_openai_reasoning_model(model)
                      else _OPENROUTER_MAX_TOKENS)
    last: Exception | None = None
    is_openrouter = "openrouter.ai" in _OPENROUTER_BASE_URL
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        # Cap the completion budget. The agent only emits a small JSON
        # object per turn, so ~512 tokens is ample — and it stops
        # OpenRouter from *reserving* the model's full 16k-token budget
        # against the account balance, which caused HTTP 402
        # "requires more credits, or fewer max_tokens" once free credit
        # ran low.
        "max_tokens": max_tokens,
    }
    if not is_openrouter and _is_openai_reasoning_model(model):
        # Talking to OpenAI directly (real OpenRouter normalises this for
        # you): reasoning-tier models rename the completion-budget param and
        # only accept the default temperature (1) — sending 0 400s.
        body["max_completion_tokens"] = body.pop("max_tokens")
        del body["temperature"]
    if is_openrouter:
        # Ask OpenRouter to include the USD cost in the usage block. Other
        # OpenAI-compatible gateways (OpenAI itself, Portkey, ...) 400 on this
        # unrecognised field, so it's only sent when actually talking to OpenRouter.
        body["usage"] = {"include": True}
    for attempt in range(max_retries):
        key = _next_key()  # rotate keys to spread per-key rate limits
        try:
            resp = requests.post(
                _OPENROUTER_BASE_URL,
                headers=_gateway_headers(key),
                json=body,
                timeout=120,
            )
            if resp.status_code == 200:
                content, usage = _parse_response(resp)
                if content is not None:
                    pt, ct, cost = _usage_fields(usage, model)
                    return LLMResult(content, pt, ct, cost)
                # 200 OK but no usable completion; treat as transient and retry.
                last = RuntimeError(f"OpenRouter 200 without content: {resp.text[:160]}")
                time.sleep(_backoff(attempt))
                continue
            if resp.status_code == 402:
                # This key is out of credit ("requires more credits"). Rotate to
                # the NEXT key immediately (no backoff — more money won't appear by
                # waiting); with several funded keys the run routes around the dry
                # one. If every key is exhausted we fail fast after the retries.
                last = LLMError(f"HTTP 402: {resp.text[:160]}")
                continue
            if resp.status_code in (429, 500, 502, 503):
                last = LLMError(f"HTTP {resp.status_code}: {resp.text[:160]}")
                time.sleep(_backoff(attempt))
                continue
            raise LLMError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as e:
            last = e
            time.sleep(_backoff(attempt))
    raise LLMError(f"OpenRouter unavailable after {max_retries} attempts: {last}")


# --------------------------------------------------------------------------
# Anthropic backend (native Claude API)
# --------------------------------------------------------------------------
_anthropic_client = None


def _anthropic_sdk():
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic
        except ImportError as e:   # noqa: BLE001
            raise LLMError(
                "The Anthropic backend needs the official SDK: pip install -e \".[anthropic]\""
            ) from e
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise LLMError("No ANTHROPIC_API_KEY configured in .env")
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _anthropic_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """USD for one call, from the published per-million rates."""
    for name, (per_m_in, per_m_out) in ANTHROPIC_PRICES.items():
        if model.startswith(name):
            return prompt_tokens / 1e6 * per_m_in + completion_tokens / 1e6 * per_m_out
    return 0.0   # unknown model: record the tokens, don't invent a price


def _anthropic_text(content) -> str:
    """Concatenate the text blocks of a response.

    A response also carries ``thinking`` blocks; their text is empty unless
    summarized display is requested, and they are not part of the answer either
    way — the agent's JSON action lives in the text blocks.
    """
    return "".join(
        block.text for block in content
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    )


# Per-model params Anthropic has actually rejected at runtime (learned, not
# guessed). `effort` and the server-side-fallback beta turned out to be two
# *independent* capabilities — claude-opus-4-8 accepts effort but rejects
# fallbacks, which accepts_effort()'s single reasoning-model heuristic can't
# predict. Rather than hardcode a second allowlist we're not certain of,
# unsupported params are learned on first 400 and never resent for that model.
_unsupported_params: dict[str, set[str]] = {}
_unsupported_param_re = re.compile(r"does not support the `(\w+)` parameter")


def _strip_unsupported(request: dict, model: str) -> None:
    """Remove any param already known-unsupported by ``model`` from ``request``."""
    known = _unsupported_params.get(model)
    if not known:
        return
    if "effort" in known:
        request.pop("output_config", None)
    if "fallbacks" in known or "betas" in known:
        request.pop("fallbacks", None)
        request.pop("betas", None)


def _learn_unsupported(model: str, error_text: str) -> str | None:
    """If ``error_text`` names an unsupported param, remember it. Returns the
    param name if one was learned (caller should retry), else None."""
    m = _unsupported_param_re.search(error_text)
    if not m:
        return None
    param = m.group(1)
    _unsupported_params.setdefault(model, set()).add(param)
    return param


def _anthropic(messages: list[Message], model: str, max_retries: int,
               temperature: float | None = None, max_tokens: int | None = None) -> LLMResult:
    client = _anthropic_sdk()
    system, turns = _split_system_blocks(messages)
    max_tokens = max_tokens or _ANTHROPIC_MAX_TOKENS

    request: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": turns,
    }
    if system:
        request["system"] = system
    if temperature is not None and accepts_temperature(model):
        request["temperature"] = temperature
    # Effort (the cost/depth dial) and server-side fallbacks are both features
    # of the extended-thinking model family (see accepts_effort) — a smaller
    # non-reasoning model like claude-haiku-4-5 400s on either. Even within
    # that family, support isn't uniform (see _unsupported_params above), so
    # _strip_unsupported prunes anything already learned-unsupported for model.
    if accepts_effort(model):
        request["output_config"] = {"effort": ANTHROPIC_EFFORT}
        # Ariadne traces Active Directory attack paths, which sits squarely in
        # the domain the cyber safety classifiers watch. A refused request comes
        # back as a normal 200 with stop_reason="refusal", so opting into
        # server-side fallbacks means a benign run gets answered by the fallback
        # model instead of dying on a false positive.
        request["betas"] = ["server-side-fallback-2026-07-01"]
        request["fallbacks"] = "default"
    _strip_unsupported(request, model)

    last: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.beta.messages.create(**request)
        except Exception as e:  # noqa: BLE001 — mapped to LLMError below
            last = e
            status = getattr(e, "status_code", None)
            # A credit-exhausted account reports 400, not 402 like OpenRouter,
            # and the raw body buries the reason in a JSON dump. Name it.
            if "credit balance is too low" in str(e):
                raise LLMError(
                    "Anthropic rejected the request: the account has no API credit. "
                    "Add credit at console.anthropic.com -> Plans & Billing (an API key "
                    "alone does not carry a balance; a Claude.ai subscription is separate)."
                ) from e
            # An unsupported-param 400 is learned and stripped, then retried
            # immediately — no point burning the retry budget on backoff for a
            # request that will fail identically every time otherwise.
            if status == 400 and _learn_unsupported(model, str(e)):
                _strip_unsupported(request, model)
                continue
            # Any other 4xx except rate limiting is a bad request: retrying
            # unchanged just burns the retry budget.
            if status is not None and 400 <= status < 500 and status != 429:
                raise LLMError(f"Anthropic HTTP {status}: {e}") from e
            time.sleep(_backoff(attempt))
            continue

        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) or "unspecified"
            raise LLMError(
                f"Anthropic declined this request (category: {category}). Ariadne's "
                f"domain — Active Directory attack paths — can trip the cyber "
                f"classifiers even on synthetic data."
            )

        usage = getattr(response, "usage", None)
        pt = int(getattr(usage, "input_tokens", 0) or 0)
        ct = int(getattr(usage, "output_tokens", 0) or 0)
        return LLMResult(_anthropic_text(response.content), pt, ct,
                         _anthropic_cost(model, pt, ct))

    raise LLMError(f"Anthropic unavailable after {max_retries} attempts: {last}")


# --------------------------------------------------------------------------
# Gemini backend (native free tier, throttled)
# --------------------------------------------------------------------------
_MAX_PER_MIN = int(os.getenv("GEMINI_MAX_RPM", "14"))
_WINDOW = 60.0
_call_times: deque[float] = deque()
_genai_client = None


def _gemini_client():
    global _genai_client
    if _genai_client is None:
        from google import genai

        _genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _genai_client


def _throttle() -> None:
    now = time.monotonic()
    while _call_times and now - _call_times[0] > _WINDOW:
        _call_times.popleft()
    if len(_call_times) >= _MAX_PER_MIN:
        wait = _WINDOW - (now - _call_times[0]) + 0.2
        if wait > 0:
            time.sleep(wait)
        now = time.monotonic()
        while _call_times and now - _call_times[0] > _WINDOW:
            _call_times.popleft()
    _call_times.append(time.monotonic())


def _retry_delay(err: Exception) -> float:
    s = str(err)
    m = re.search(r"retry in ([0-9.]+)s", s) or re.search(r"retryDelay['\"]?:\s*'?([0-9.]+)s", s)
    return float(m.group(1)) + 1.0 if m else 20.0


def _split_system(messages: list[Message]) -> tuple[str | None, str]:
    """Separate the system prompt from the conversation.

    Gemini takes the system prompt in its own slot. Flattening it into the
    conversation text (as this used to) meant the Gemini agent ran on a
    materially different prompt from the OpenRouter one — the system role became
    an untagged first line — so the two backends weren't comparable.
    """
    system_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    turns = []
    for m in messages:
        role = m.get("role", "user")
        if role == "system":
            continue
        content = m.get("content", "")
        turns.append(f"Assistant: {content}" if role == "assistant" else content)
    return ("\n".join(system_parts) or None), "\n".join(turns)


def _messages_to_prompt(messages: list[Message]) -> str:
    """Flatten role-tagged messages into a single prompt string (Gemini path)."""
    system, turns = _split_system(messages)
    return "\n".join(p for p in (system, turns) if p)


def _gemini(messages: list[Message], model: str, max_retries: int,
            temperature: float | None = None) -> LLMResult:
    system, prompt = _split_system(messages)
    temperature = _client.temperature if temperature is None else temperature
    last: Exception | None = None
    for attempt in range(max_retries):
        _throttle()
        try:
            # Honour the configured temperature here too. It used to be dropped
            # on this path, so `--temperature 0.7` silently did nothing on Gemini
            # and a "variance" sweep produced identical runs.
            config: dict = {"temperature": temperature}
            if system:
                config["system_instruction"] = system
            resp = _gemini_client().models.generate_content(
                model=model, contents=prompt, config=config,
            )
            um = getattr(resp, "usage_metadata", None)
            pt = int(getattr(um, "prompt_token_count", 0) or 0)
            ct = int(getattr(um, "candidates_token_count", 0) or 0)
            return LLMResult(resp.text, pt, ct, 0.0)   # free tier: no cost
        except Exception as e:  # noqa: BLE001
            last = e
            rate_limited = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            time.sleep(_retry_delay(e) if rate_limited else _backoff(attempt))
    raise LLMError(f"Gemini unavailable after {max_retries} attempts: {last}")


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------
def chat(messages: list[Message], *, max_retries: int | None = None) -> LLMResult:
    """Run one chat completion over role-tagged messages, with usage accounting."""
    return _client.chat(messages, max_retries=max_retries)


def ask_llm(prompt: str, *, max_retries: int | None = None) -> str:
    """Single-turn convenience wrapper returning just the completion text."""
    return chat([{"role": "user", "content": prompt}], max_retries=max_retries).text
