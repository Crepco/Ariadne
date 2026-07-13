# tests/

Manual smoke checks for each component — not a `pytest` suite. Each script exercises
one piece against a **live Neo4j** (see `.env`) and, where relevant, a **live LLM**
(needs an API key), then prints what it got back. Run them individually from the repo
root with the project's Python:

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
