"""Shared fixtures/helpers for the offline unit tests.

These tests never touch Neo4j or an LLM API — they exercise the pure logic
(graph construction, path parsing, scoring, metrics, logging). The generator
lives outside the ``ariadne`` package (``data/generator/generate.py``), so make
it importable as ``generate``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _sub in ("data/generator", "data/ingest"):
    _p = str(_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
