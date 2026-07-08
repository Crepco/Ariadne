# src/ariadne/agent/

The LLM agent — a minimal, custom **ReAct loop**: reason → call a tool → observe the result → repeat, until it proposes an attack path or hits a step budget.

Deliberately lightweight. The point of the study is to measure the *model's* reasoning over the graph, so the scaffolding around it stays thin and legible.

## Responsibilities

- Hold the system prompt: the goal, the rules, and the available tools ([`../tools/`](../tools/)).
- Drive the reason/act/observe loop against one LLM via its native tool-use API.
- Enforce guardrails: max steps / max tool calls, timeout, output format.
- Emit a structured final answer — an ordered list of hops, each with a one-line justification.

## LLM access

- Primary: Anthropic API (Claude) — use the latest Claude models.
- Optional: a second provider (e.g. OpenAI) to enable a model-vs-model comparison.
- Keys come from `.env` via the shared `config.py`; never hard-code them.

## To add

- `loop.py` — the ReAct control loop.
- `prompts.py` — system prompt + output-format instructions.
- `llm.py` — provider abstraction so a second model can be dropped in.
- A `run(start_node, goal)` entry point that hands its result to [`../evaluation/`](../evaluation/).
