"""LLM access for the agent.

Two backends:

* **OpenRouter** (default when ``OPENROUTER_API_KEYS`` is set) — an OpenAI-compatible
  endpoint that fronts many models. Keys are rotated round-robin to spread rate
  limits; the model is configurable via ``OPENROUTER_MODEL`` or ``set_model()``.
* **Gemini** (native free tier) — throttled to stay under 15 requests/min.

``chat(messages)`` is the primary entry point: it takes role-tagged messages
(``system`` / ``user`` / ``assistant``) and returns an :class:`LLMResult` carrying
the completion text plus token/cost usage. ``ask_llm(prompt)`` is a thin
single-turn wrapper that returns just the text. ``active_model()`` reports which
model is live (for logging) and ``set_model()`` switches it (for multi-model
benchmarks).
"""

from __future__ import annotations

import itertools
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass

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
    raw = os.getenv("OPENROUTER_API_KEYS") or os.getenv("OPENROUTER_API_KEY") or ""
    return [k.strip() for k in raw.split(",") if k.strip()]


_OPENROUTER_KEYS = _load_keys()
_key_cycle = itertools.cycle(_OPENROUTER_KEYS) if _OPENROUTER_KEYS else None
_key_lock = threading.Lock()

GEMINI_MODEL = "gemini-3.1-flash-lite"
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
_OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "512"))

_default_provider = os.getenv("LLM_PROVIDER") or ("openrouter" if _OPENROUTER_KEYS else "gemini")
_state = {
    "provider": _default_provider,
    "model": DEFAULT_OPENROUTER_MODEL if _default_provider == "openrouter" else GEMINI_MODEL,
}

# Back-compat snapshot; prefer active_model() for the live value.
MODEL_NAME = _state["model"]


def active_model() -> str:
    return _state["model"]


def set_model(model: str, provider: str | None = None) -> None:
    """Switch the model chat/ask_llm uses. Infers the provider from the slug shape
    (``vendor/model`` -> OpenRouter) unless one is given explicitly."""
    global MODEL_NAME
    _state["model"] = model
    _state["provider"] = provider or ("openrouter" if "/" in model else "gemini")
    MODEL_NAME = model


def _messages_to_prompt(messages: list[Message]) -> str:
    """Flatten role-tagged messages into a single prompt string (Gemini path)."""
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"Assistant: {content}" if role == "assistant" else content)
    return "\n".join(parts)


# --------------------------------------------------------------------------
# OpenRouter backend
# --------------------------------------------------------------------------
def _next_key() -> str:
    with _key_lock:
        return next(_key_cycle)


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


def _usage_fields(usage: dict) -> tuple[int, int, float]:
    return (
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
        float(usage.get("cost") or 0.0),   # OpenRouter reports cost in USD
    )


def _openrouter(messages: list[Message], model: str, max_retries: int) -> LLMResult:
    if not _OPENROUTER_KEYS:
        raise LLMError("No OPENROUTER_API_KEYS configured in .env")
    last: Exception | None = None
    for attempt in range(max_retries):
        key = _next_key()  # rotate keys to spread per-key rate limits
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "X-Title": "Ariadne",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0,
                    # Cap the completion budget. The agent only emits a small JSON
                    # object per turn, so ~512 tokens is ample — and it stops
                    # OpenRouter from *reserving* the model's full 16k-token budget
                    # against the account balance, which caused HTTP 402
                    # "requires more credits, or fewer max_tokens" once free credit
                    # ran low.
                    "max_tokens": _OPENROUTER_MAX_TOKENS,
                    # Ask OpenRouter to include the USD cost in the usage block.
                    "usage": {"include": True},
                },
                timeout=120,
            )
            if resp.status_code == 200:
                content, usage = _parse_response(resp)
                if content is not None:
                    pt, ct, cost = _usage_fields(usage)
                    return LLMResult(content, pt, ct, cost)
                # 200 OK but no usable completion; treat as transient and retry.
                last = RuntimeError(f"OpenRouter 200 without content: {resp.text[:160]}")
                time.sleep(min(20.0, 2 + attempt * 3))
                continue
            if resp.status_code == 402:
                # This key is out of credit ("requires more credits"). Rotate to
                # the NEXT key immediately (no backoff — more money won't appear by
                # waiting); with several funded keys the run routes around the dry
                # one. If every key is exhausted we fail fast after the retries.
                last = RuntimeError(f"HTTP 402: {resp.text[:160]}")
                continue
            if resp.status_code in (429, 500, 502, 503):
                last = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:160]}")
                time.sleep(min(20.0, 2 + attempt * 3))
                continue
            raise LLMError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as e:
            last = e
            time.sleep(min(20.0, 2 + attempt * 3))
    raise LLMError(f"OpenRouter unavailable after {max_retries} attempts: {last}")


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


def _gemini(messages: list[Message], model: str, max_retries: int) -> LLMResult:
    prompt = _messages_to_prompt(messages)
    last: Exception | None = None
    for attempt in range(max_retries):
        _throttle()
        try:
            resp = _gemini_client().models.generate_content(model=model, contents=prompt)
            um = getattr(resp, "usage_metadata", None)
            pt = int(getattr(um, "prompt_token_count", 0) or 0)
            ct = int(getattr(um, "candidates_token_count", 0) or 0)
            return LLMResult(resp.text, pt, ct, 0.0)   # free tier: no cost
        except Exception as e:  # noqa: BLE001
            last = e
            rate_limited = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            time.sleep(_retry_delay(e) if rate_limited else 3.0)
    raise LLMError(f"Gemini unavailable after {max_retries} attempts: {last}")


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------
# Default a bit above the number of rotated keys so a single call can try each
# funded key once (402/rate-limit retries rotate the key each attempt).
_DEFAULT_MAX_RETRIES = max(6, len(_OPENROUTER_KEYS) + 1)


def chat(messages: list[Message], *, max_retries: int = _DEFAULT_MAX_RETRIES) -> LLMResult:
    """Run one chat completion over role-tagged messages, with usage accounting."""
    if _state["provider"] == "openrouter":
        return _openrouter(messages, _state["model"], max_retries)
    return _gemini(messages, _state["model"], max_retries)


def ask_llm(prompt: str, *, max_retries: int = _DEFAULT_MAX_RETRIES) -> str:
    """Single-turn convenience wrapper returning just the completion text."""
    return chat([{"role": "user", "content": prompt}], max_retries=max_retries).text
