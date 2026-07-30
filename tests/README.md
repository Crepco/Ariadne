# tests/

Two kinds of tests live here.

## `tests/unit/` — offline unit suite (default `pytest` target)

Assertion-based tests for the pure logic (graph construction, name resolution,
JSON/path parsing, the hop-by-hop walk, metrics aggregation and confidence
intervals, CSV logging, LLM response handling, benchmark failure classification).
They touch **neither Neo4j nor any LLM API**, so they run anywhere in seconds:

```bash
pip install -e ".[dev]"    # installs pytest
pytest                     # runs tests/unit/ only (see pyproject testpaths)
```

## `tests/smoke/` — manual scripts, need a live backend

The scripts under `tests/smoke/` are manual smoke checks. Each exercises one
piece against a **live Neo4j** (see `.env`) and, where relevant, a **live LLM**
(needs an API key), then prints what it got back. They are named `smoke_*.py`
rather than `test_*.py` so `pytest` never collects them — under the old names
they shadowed the unit tests of the same basename, and `pytest tests/` failed
with an import-file mismatch.

Run them individually from the repo root with the project's Python:

```bash
python tests/smoke/smoke_tools.py     # the 6 graph tools against the current graph
python tests/smoke/smoke_score.py     # path scoring on a known planted chain
python tests/smoke/smoke_agent.py     # one full ReAct agent run
python tests/smoke/smoke_logger.py    # append a row to the results log
python tests/smoke/smoke_metrics.py   # aggregate whatever is in the log
python tests/smoke/smoke_llm.py       # a single LLM round-trip
```

They assume a graph has already been generated (`python data/generator/generate.py --wipe`).
If your graph predates the shared `:Base` label, backfill it once with
`python data/generator/migrate_base_label.py` — without it, every id lookup falls
back to a full scan.
For an actual end-to-end run use [`run.py`](../run.py); for the full benchmark use
[`experiments/run_benchmark.py`](../experiments/run_benchmark.py).