# tests/

Two kinds of tests live here.

## `tests/unit/` — offline unit suite (default `pytest` target)

Assertion-based tests for the pure logic (graph construction, JSON/path parsing,
hop-by-hop scoring, metrics aggregation, CSV logging, LLM response handling).
They touch **neither Neo4j nor any LLM API**, so they run anywhere in seconds:

```bash
pip install -e ".[dev]"    # installs pytest
pytest                     # runs tests/unit/ only (see pyproject testpaths)
```

## Top-level smoke scripts — manual, need a live backend

The scripts directly under `tests/` are manual smoke checks. Each exercises one
piece against a **live Neo4j** (see `.env`) and, where relevant, a **live LLM**
(needs an API key), then prints what it got back. They are *not* collected by
`pytest`; run them individually from the repo root with the project's Python:

```bash
python tests/test_tools.py     # the 4 graph-query tools against the current graph
python tests/test_score.py     # path scoring on a known planted chain
python tests/test_agent.py     # one full ReAct agent run
python tests/test_logger.py    # append a row to the results log
python tests/test_metrics.py   # aggregate whatever is in the log
python tests/test_llm.py       # a single LLM round-trip
```

They assume a graph has already been generated (`python data/generator/generate.py --wipe`).
For an actual end-to-end run use [`run.py`](../run.py); for the full benchmark use
[`experiments/run_benchmark.py`](../experiments/run_benchmark.py).