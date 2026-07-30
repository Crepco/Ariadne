"""Offline tests for the benchmark runner's failure classification.

Whether a failed run is retried or dropped decides the denominator of every rate
in the results table, so the classification is worth pinning down.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "experiments"))

run_benchmark = pytest.importorskip("run_benchmark")

from ariadne.agent.llm import LLMError  # noqa: E402


def _fake_result():
    """A stand-in AgentResult with the telemetry fields run_one reads."""
    return SimpleNamespace(tool_calls=3, steps=4, max_steps=20, elapsed_seconds=1.5,
                           prompt_tokens=10, completion_tokens=5, cost_usd=0.001)


@pytest.mark.parametrize("exc", [
    LLMError("OpenRouter unavailable after 6 attempts"),
    RuntimeError("HTTP 402: requires more credits"),
    RuntimeError("HTTP 429: rate limit exceeded"),
    RuntimeError("Connection aborted"),
    TimeoutError("request timed out"),
    Exception("RESOURCE_EXHAUSTED"),
])
def test_infrastructure_failures_are_retryable(exc):
    assert run_benchmark.is_infrastructure_error(exc) is True


@pytest.mark.parametrize("exc", [
    KeyError("goal_oid"),
    ValueError("Unknown edge type: 'Bogus'"),
    AttributeError("'NoneType' object has no attribute 'objectid'"),
])
def test_agent_and_code_failures_are_not_retryable(exc):
    # These are real failures. Retrying hides a bug; dropping them from the
    # metrics would flatter the model. They must be scored as misses.
    assert run_benchmark.is_infrastructure_error(exc) is False


def test_run_one_records_a_scored_row_on_first_success(monkeypatch):
    monkeypatch.setattr(run_benchmark, "run_agent",
                        lambda name, max_steps=None, verbose=False: _fake_result())
    monkeypatch.setattr(run_benchmark, "score_agent_result",
                        lambda ctx, result, oid: {"correct": True, "path_valid": True})
    row = run_benchmark.run_one(None, {"name": "U@D", "oid": "o1", "kind": "planted"}, 100, 20)
    assert row["error"] == ""
    assert row["attempts"] == 1
    assert row["correct"] is True


def test_run_one_retries_an_infrastructure_failure_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky(name, max_steps=None, verbose=False):
        calls["n"] += 1
        if calls["n"] == 1:
            raise LLMError("HTTP 429: rate limit")
        return _fake_result()

    monkeypatch.setattr(run_benchmark, "run_agent", flaky)
    monkeypatch.setattr(run_benchmark, "score_agent_result",
                        lambda ctx, result, oid: {"correct": True})
    monkeypatch.setattr(run_benchmark.time, "sleep", lambda s: None)

    row = run_benchmark.run_one(None, {"name": "U@D", "oid": "o1", "kind": "planted"}, 100, 20,
                                infra_retries=2)
    assert calls["n"] == 2
    assert row["error"] == ""
    assert row["attempts"] == 2      # the retry is recorded, not hidden


def test_run_one_does_not_retry_a_genuine_failure(monkeypatch):
    calls = {"n": 0}

    def broken(name, max_steps=None, verbose=False):
        calls["n"] += 1
        raise ValueError("bad graph")

    monkeypatch.setattr(run_benchmark, "run_agent", broken)
    monkeypatch.setattr(run_benchmark.time, "sleep", lambda s: None)

    row = run_benchmark.run_one(None, {"name": "U@D", "oid": "o1", "kind": "planted"}, 100, 20,
                                infra_retries=2)
    assert calls["n"] == 1
    assert "bad graph" in row["error"]
