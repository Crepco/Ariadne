import os
import re
import time
from collections import deque

from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Single source of truth for the model id, so logging/metrics record what ran.
MODEL_NAME = "gemini-3.1-flash-lite"

# The Gemini free tier allows 15 requests/min; stay just under it with a rolling
# 60s window so a benchmark of many runs doesn't trip 429 RESOURCE_EXHAUSTED.
_MAX_PER_MIN = int(os.getenv("GEMINI_MAX_RPM", "14"))
_WINDOW = 60.0
_call_times: deque[float] = deque()


class LLMError(RuntimeError):
    """Raised when the model can't be reached after exhausting retries."""


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
    """Pull the server-suggested wait out of a 429, else a sane default."""
    s = str(err)
    m = re.search(r"retry in ([0-9.]+)s", s) or re.search(r"retryDelay['\"]?:\s*'?([0-9.]+)s", s)
    if m:
        return float(m.group(1)) + 1.0
    return 20.0


def ask_llm(prompt: str, *, max_retries: int = 6) -> str:
    """Call Gemini, throttled and with retry/backoff on rate limits."""
    last: Exception | None = None
    for attempt in range(max_retries):
        _throttle()
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            return response.text
        except Exception as e:  # noqa: BLE001 - surface everything as a retryable call
            last = e
            rate_limited = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            delay = _retry_delay(e) if rate_limited else 3.0
            print(f"Gemini call failed (attempt {attempt + 1}/{max_retries}); waiting {delay:.0f}s")
            time.sleep(delay)
    raise LLMError(f"Gemini unavailable after {max_retries} attempts: {last}")
