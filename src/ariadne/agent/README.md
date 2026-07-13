# src/ariadne/agent/

The LLM agent — a minimal, custom **ReAct loop**: reason → call a tool → observe the
result → repeat, until it proposes an attack path or hits the step budget. Deliberately
lightweight, so what's measured is the *model's* reasoning over the graph, not clever
scaffolding.

## Modules

| File | Role |
| --- | --- |
| `loop.py` | The ReAct control loop. Returns an `AgentResult` with the proposed path and real telemetry (tool calls, steps, wall-clock time). |
| `prompts.py` | System prompt: the goal, the rules ("never invent edges"), the tools, and the JSON action format. |
| `llm.py` | LLM backend + `ask_llm()`. Defaults to **OpenRouter** (any model, keys rotated); optional native **Gemini**. `active_model()` / `set_model()` support multi-model benchmarks. |
| `tool_registry.py` | Maps action names to the tool functions in [`../tools/`](../tools/). |

## The loop

Each turn the model returns one JSON object — either an action
(`{"action": "query_outbound_edges", "input": "..."}`) or a finish
(`{"action": "finish", "answer": "...", "path": [...]}`). The loop executes the tool, feeds
the observation back, and repeats up to `MAX_STEPS`. A run that never finishes is recorded
as *incomplete* — distinct from a wrong or hallucinated answer.

## LLM backend

Configured entirely through `.env` (see [`.env.example`](../../../.env.example)): set
`OPENROUTER_API_KEYS` (one or more, comma-separated) to use OpenRouter, or `GEMINI_API_KEY`
with `LLM_PROVIDER=gemini`. Keys are never hard-coded.
