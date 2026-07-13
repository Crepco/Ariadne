# src/ariadne/tools/

The graph-query tools the agent is given — the bridge between the LLM and Neo4j. Each is a
small Python function wrapping a Cypher query ([`tools.py`](tools.py)), exposed to the model
through the ReAct loop's action protocol.

**Design principle:** the agent is *not* handed the whole graph as text — that would reduce
the task to text pattern-matching. It must explore, exactly like a human clicking through
BloodHound.

## The four tools

| Tool | What it returns |
| --- | --- |
| `search_node(name_or_type)` | Find a user, group, or computer by name or label |
| `query_outbound_edges(objectid)` | What this object can control / reach |
| `query_inbound_edges(objectid)` | What can control / reach this object |
| `check_path_exists(start, goal)` | Whether a chain actually exists between two objects |

`check_path_exists` is dual-use: the agent can self-check with it, and the scoring harness
([`../evaluation/`](../evaluation/)) uses the same `shortestPath` primitive as the
ground-truth baseline. All tools go through the shared driver in
[`../db.py`](../db.py) and honour the configured `NEO4J_DATABASE`.
