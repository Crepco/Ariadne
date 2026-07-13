# src/ariadne/

The Python package: the agent, its tools, and the evaluation harness.

## Modules

| Path | Role |
| --- | --- |
| [`tools/`](tools/) | The 4 graph-query tools — Cypher wrapped as callable functions the agent invokes |
| [`agent/`](agent/) | The ReAct loop, prompts, and LLM backend (reason → call tool → observe → repeat) |
| [`evaluation/`](evaluation/) | Hop-by-hop scoring, per-run logging, metrics, and plots |
| `config.py` | Load Neo4j credentials (and defaults) from `.env` — single source of truth |
| `db.py` | Thin Neo4j driver/session wrapper shared by the generator, tools, and scoring |
| `schema.py` | The BloodHound node labels, edge types, and the traversable-edge set |

Installed editable (`pip install -e .`) so `import ariadne` works everywhere.

## One run, end to end

1. Pick a starting node ("user A has just been phished"); the goal is always Domain Admins.
2. The agent calls tools to explore outward from A, one hop at a time.
3. It reasons about which relationships chain toward the goal.
4. It proposes an ordered attack path (or declares no path exists).
5. Scoring verifies the path edge by edge against the graph and compares it to the
   ground-truth shortest path, recording correctness, hallucination, tool calls, and time.
