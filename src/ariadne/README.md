# src/ariadne/

The Python package: the agent, its tools, and the evaluation harness. This is pieces **3** and **4** of the architecture (the query-tool layer and the LLM agent), plus scoring.

## Modules

| Path | Role |
| --- | --- |
| [`tools/`](tools/) | The 4 graph-query tools — Cypher wrapped as callable functions the agent can invoke |
| [`agent/`](agent/) | The ReAct loop and LLM access (reason → call tool → observe → repeat) |
| [`evaluation/`](evaluation/) | Scoring, per-run logging, and metric computation |

## Planned shared pieces

- `config.py` — load Neo4j credentials and API keys from `.env`.
- `db.py` — a thin Neo4j driver/session wrapper the tools and scoring share.
- `schema.py` — the BloodHound node/edge vocabulary in scope (node labels, edge types).

## One run, end to end

1. Pick a starting node ("user A has just been phished") and a goal ("any Domain Admin").
2. The agent calls tools to explore outward from user A.
3. It reasons about which relationships chain toward the goal.
4. It outputs a proposed attack path (ordered hops) with a short justification per hop.
5. The scoring script confirms whether the path is real, and records time, tool-call count, and whether it matches/beats BloodHound's answer.

> No implementation yet — each subfolder's README describes what goes there.
