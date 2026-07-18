"""Offline tests for the CSV run logger (writes to a temp file, no database)."""

from __future__ import annotations

import csv

from ariadne.evaluation import logger


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_writes_header_and_all_fields(tmp_path):
    p = tmp_path / "out.csv"
    logger.log_row({"model": "m", "graph_size": 210, "correct": True}, path=p)
    rows = _read(p)
    assert len(rows) == 1
    assert set(rows[0].keys()) == set(logger.FIELDS)
    assert rows[0]["model"] == "m"


def test_missing_columns_become_empty(tmp_path):
    p = tmp_path / "out.csv"
    logger.log_row({"model": "m"}, path=p)
    rows = _read(p)
    assert rows[0]["correct"] == ""
    assert rows[0]["tool_calls"] == ""


def test_time_seconds_rounded(tmp_path):
    p = tmp_path / "out.csv"
    logger.log_row({"model": "m", "time_seconds": 1.234567}, path=p)
    assert _read(p)[0]["time_seconds"] == "1.235"


def test_appends_without_duplicate_header(tmp_path):
    p = tmp_path / "out.csv"
    logger.log_row({"model": "a"}, path=p)
    logger.log_row({"model": "b"}, path=p)
    rows = _read(p)
    assert [r["model"] for r in rows] == ["a", "b"]


def test_log_run_wrapper_delegates_to_log_row(monkeypatch):
    # log_run can't redirect the output path, so assert delegation instead of
    # writing (which would touch the real experiments/logs/results.csv).
    captured = {}
    monkeypatch.setattr(logger, "log_row", lambda row, path=None: captured.update(row))
    logger.log_run(model="m", correct=True, tool_calls=4)
    assert captured["model"] == "m"
    assert captured["tool_calls"] == 4
