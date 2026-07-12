"""Minimal ReAct agent loop with run telemetry.

``run_agent`` drives the reason -> act -> observe cycle and returns an
``AgentResult`` carrying everything the evaluation layer needs: the final
answer, the structured path the agent proposed (if any), and *real* counters
(tool calls, reasoning steps, wall-clock time). Those counters used to be
hardcoded in ``run.py``; now they come from the run itself.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from .llm import ask_llm
from .prompts import SYSTEM_PROMPT
from .tool_registry import TOOLS

MAX_STEPS = 12


@dataclass
class AgentResult:
    answer: str                    # final answer text (or status message)
    finished: bool                 # did the agent emit an explicit finish?
    path_field: list[str] | None   # structured node list if the agent gave one
    tool_calls: int                # graph queries the agent actually ran
    steps: int                     # reasoning steps taken
    elapsed_seconds: float         # wall-clock time for the whole run
    transcript: list[dict] = field(default_factory=list)

    def __str__(self) -> str:  # keeps run.py / test_agent.py prints readable
        return self.answer


def _user_preamble(start_node: str) -> str:
    return f"""
Starting node: {start_node}

Available tools: search_node, query_outbound_edges, query_inbound_edges, check_path_exists

Respond with ONE JSON object per turn.

To act:
{{ "action": "query_outbound_edges", "input": "S-1-5-21-...-900001" }}

When done, report the ordered NODE NAMES you walked (start -> ... -> DOMAIN ADMINS):
{{ "action": "finish", "answer": "A -> B -> DOMAIN ADMINS", "path": ["A", "B", "DOMAIN ADMINS"] }}

If no path to DOMAIN ADMINS exists:
{{ "action": "finish", "answer": "NO PATH FOUND", "path": [] }}
"""


def run_agent(start_node: str, *, verbose: bool = True) -> AgentResult:
    """Run the ReAct loop from ``start_node`` and return structured telemetry."""
    history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_preamble(start_node)},
    ]

    tool_calls = 0
    started = time.perf_counter()

    for step in range(MAX_STEPS):
        if verbose:
            print(f"\n========== STEP {step + 1} ==========")

        prompt = "\n".join(m["content"] for m in history)
        response = ask_llm(prompt)
        if verbose:
            print("LLM:")
            print(response)

        history.append({"role": "assistant", "content": response})

        action = _parse_json(response)
        if action is None:
            # Model didn't return usable JSON; treat the raw text as the answer.
            return _result(response.strip(), False, None, tool_calls, step + 1, started, history)

        if action.get("action") == "finish":
            return _result(
                str(action.get("answer", "")).strip(),
                True,
                _as_str_list(action.get("path")),
                tool_calls,
                step + 1,
                started,
                history,
            )

        tool = action.get("action")
        argument = action.get("input", "")

        if tool not in TOOLS:
            observation = f"Unknown tool: {tool}. Valid tools: {', '.join(TOOLS)}."
        else:
            if verbose:
                print(f"\nCalling {tool}({argument})")
            tool_calls += 1
            try:
                observation = TOOLS[tool](argument)
            except Exception as e:  # a bad tool call shouldn't kill the whole run
                observation = f"Tool error: {e}"
        if verbose:
            print(observation)

        history.append({"role": "user", "content": f"Observation:\n{observation}"})

    return _result("Maximum reasoning steps exceeded.", False, None, tool_calls, MAX_STEPS, started, history)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _result(answer, finished, path_field, tool_calls, steps, started, history) -> AgentResult:
    return AgentResult(
        answer=answer,
        finished=finished,
        path_field=path_field,
        tool_calls=tool_calls,
        steps=steps,
        elapsed_seconds=time.perf_counter() - started,
        transcript=history,
    )


def _parse_json(text: str):
    """Parse a JSON object, tolerating prose or ```json code fences around it."""
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
        return None


def _as_str_list(v):
    return [str(x) for x in v] if isinstance(v, list) else None
