# src/ariadne/tools/

The graph-query tools the agent is given — the bridge between the LLM and Neo4j. Each is a small Python function wrapping a Cypher query, exposed to the model through the native function-calling / tool-use API.

**Design principle:** the agent is *not* handed the whole graph as text — that would reduce the task to text pattern-matching. It must explore, exactly like a human clicking through BloodHound.

## The four tools

| Tool | What it returns |
| --- | --- |
| `query_outbound_edges(node)` | What this object can control / reach (full-control, member-of, reset-password, …) |
| `query_inbound_edges(node)` | What can control / reach this object |
| `search_node(name_or_type)` | Find a user, group, or computer by name or type |
| `check_path_exists(start, end)` | Verify whether a proposed chain actually exists in the graph |

`check_path_exists` is dual-use: the agent can self-check with it, and the scoring harness ([`../evaluation/`](../evaluation/)) uses the same primitive to validate proposed paths.

## To add

- One module per tool (or a single `tools.py`) wrapping Cypher via the shared `db.py`.
- JSON tool schemas / definitions passed to the model.
- Unit tests hitting a small fixed graph so each tool is validated in isolation before the agent uses it.
