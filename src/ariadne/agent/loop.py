"""Minimal ReAct agent loop with run telemetry.

``run_agent`` drives the reason -> act -> observe cycle and returns an
``AgentResult`` carrying everything the evaluation layer needs: the final
answer, the structured path the agent proposed (if any), and *real* counters
(tool calls, reasoning steps, token/cost usage, wall-clock time).

The conversation is kept as proper role-tagged messages (``system`` / ``user`` /
``assistant``) and handed to ``llm.chat`` — the model sees the system prompt, its
own prior actions, and the tool observations as distinct turns, rather than one
flattened blob.
"""

from __future__ import annotations

import inspect
import json
import time
from dataclasses import dataclass, field

from .llm import chat
from .prompts import SYSTEM_PROMPT
from .tool_registry import TOOLS

MAX_STEPS = 20      # default reasoning-step budget (was 12; large graphs need room)
MAX_REVISIONS = 2   # how many times a rejected finish may be sent back for repair


@dataclass
class AgentResult:
    answer: str                    # final answer text (or status message)
    finished: bool                 # did the agent emit an explicit finish?
    path_field: list[str] | None   # structured node list if the agent gave one
    tool_calls: int                # graph queries the agent actually ran
    steps: int                     # reasoning steps taken
    elapsed_seconds: float         # wall-clock time for the whole run
    max_steps: int = MAX_STEPS     # the step budget this run was given
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    transcript: list[dict] = field(default_factory=list)

    def __str__(self) -> str:  # keeps run.py / test_agent.py prints readable
        return self.answer


def _user_preamble(start_node: str, max_steps: int) -> str:
    return f"""
Starting node: {start_node}
Goal: reach the DOMAIN ADMINS group.

IMPORTANT: the edge tools take OBJECT IDS (like S-1-5-21-…-1234), not names. So
FIRST call search_node to resolve a name to its object id, then follow edges from
that id. Your very first action should resolve the starting node.

You have at most {max_steps} steps. Explore efficiently: from the start's object
id, follow query_outbound_edges hop by hop toward DOMAIN ADMINS. When you reach a
Computer or hit a dead end, call get_node_properties on it — a `roastable_target`,
`cred_target`, `unconstraineddelegation` or `esc1` property is an INFERRED step
(not an edge) that continues toward DOMAIN ADMINS. If forward progress stalls,
resolve DOMAIN ADMINS with search_node and work BACKWARD with query_inbound_edges.

Available tools: search_node, query_outbound_edges, query_inbound_edges, get_node_properties, check_path_exists, verify_path

Before you finish, call verify_path with your ordered path — it tells you whether
every hop is a real edge-or-inference step and names the FIRST broken one (usually a
node you skipped, e.g. the service account you roasted). Fix it, then finish. If it
says a name is AMBIGUOUS, two nodes share that short name — use the full name
search_node returned (e.g. SVC01@DOMAIN, not SVC01).

Respond with ONE JSON object per turn.

Step 1 — resolve the start node to an object id:
{{ "action": "search_node", "input": "{start_node}" }}

Then act on a REAL object id returned by the tools:
{{ "action": "query_outbound_edges", "input": "<objectid from search_node>" }}

When you think you have the path, VERIFY it first (list every node in order):
{{ "action": "verify_path", "input": ["A", "B", "DOMAIN ADMINS"] }}

Then, once verify_path says valid, report the ordered NODE NAMES you walked:
{{ "action": "finish", "answer": "A -> B -> DOMAIN ADMINS", "path": ["A", "B", "DOMAIN ADMINS"] }}

If no path to DOMAIN ADMINS exists:
{{ "action": "finish", "answer": "NO PATH FOUND", "path": [] }}
"""


def run_agent(start_node: str, *, max_steps: int = MAX_STEPS, verbose: bool = True,
              on_step=None, verify_finish: bool = True, max_revisions: int = MAX_REVISIONS) -> AgentResult:
    """Run the ReAct loop from ``start_node`` and return structured telemetry.

    ``on_step``, if given, is called after each turn with a dict
    ``{step, action, input, observation, reasoning}`` — used by the web UI to
    replay the traversal (the observation is the raw tool result, before
    stringification).
    """
    history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_preamble(start_node, max_steps)},
    ]

    tool_calls = 0
    revisions_used = 0
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
    started = time.perf_counter()

    for step in range(max_steps):
        if verbose:
            print(f"\n========== STEP {step + 1} ==========")

        result = chat(history)
        response = result.text
        usage["prompt_tokens"] += result.prompt_tokens
        usage["completion_tokens"] += result.completion_tokens
        usage["cost_usd"] += result.cost_usd
        if verbose:
            print("LLM:")
            print(response)

        history.append({"role": "assistant", "content": response})

        action = _parse_json(response)
        if action is None:
            # Model didn't return usable JSON; treat the raw text as the answer.
            return _result(response.strip(), False, None, tool_calls, step + 1, started, max_steps, usage, history)

        if action.get("action") == "finish":
            answer = str(action.get("answer", "")).strip()
            path_field = _as_str_list(action.get("path"))

            # Self-verify a proposed (non-empty) path before accepting it. If a hop
            # is not a real edge-or-inference step — the classic failure is dropping
            # the roasted service account — feed the broken hop back and let the
            # agent repair the path for up to ``max_revisions`` turns. NO-PATH
            # finishes and runs without the verifier tool are accepted unchanged.
            proposes_path = bool(path_field) and len(path_field) >= 2 and "NO PATH" not in answer.upper()
            if (verify_finish and proposes_path and revisions_used < max_revisions
                    and "verify_path" in TOOLS):
                try:
                    check = TOOLS["verify_path"](path_field)
                except Exception as e:            # never block a finish on a verifier fault
                    check = {"valid": True, "reason": f"verifier unavailable: {e}"}
                if on_step:
                    on_step({"step": step + 1, "action": "verify_path",
                             "input": " -> ".join(path_field), "observation": check,
                             "reasoning": response})
                if not check.get("valid", False):
                    revisions_used += 1
                    reason = check.get("reason", "The path could not be verified.")
                    if verbose:
                        print(f"\nverify_path REJECTED (revision {revisions_used}): {reason}")
                    history.append({"role": "user", "content":
                        "Observation:\nverify_path REJECTED your path. " + reason +
                        "\nRevise it (add the missing node or fix the hop) and call finish again."})
                    continue

            if on_step:
                on_step({"step": step + 1, "action": "finish", "input": None,
                         "observation": None, "reasoning": response})
            return _result(
                answer,
                True,
                path_field,
                tool_calls,
                step + 1,
                started,
                max_steps,
                usage,
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
            observation = _call_tool(TOOLS[tool], tool, argument)
        if verbose:
            print(observation)

        if on_step:
            on_step({"step": step + 1, "action": tool, "input": argument,
                     "observation": observation, "reasoning": response})

        history.append({"role": "user", "content": f"Observation:\n{observation}"})

    return _result("Maximum reasoning steps exceeded.", False, None, tool_calls, max_steps, started, max_steps, usage, history)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _required_params(fn) -> list[str]:
    """Parameter names a tool needs, ignoring optional ones like ``database``."""
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):      # builtins / C callables have no signature
        return []
    return [p.name for p in params
            if p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]


def _call_tool(fn, name: str, argument):
    """Invoke a tool with whatever shape the model produced, or explain the fix.

    Most tools take a single value, but ``check_path_exists`` takes two — and a
    single-positional dispatch meant every call to it raised ``TypeError`` and
    was swallowed as an opaque "Tool error", so the tool was effectively dead
    while still being advertised in the prompt. A dict input is now spread as
    keyword arguments, and a mismatch produces an observation that *names the
    parameters*, which is what lets the model retry correctly instead of
    abandoning the tool.
    """
    try:
        if isinstance(argument, dict):
            return fn(**argument)
        needed = _required_params(fn)
        if len(needed) > 1:
            return (f"{name} needs {len(needed)} arguments ({', '.join(needed)}). "
                    f"Call it with an object input, e.g. "
                    f'{{"action": "{name}", "input": {{"{needed[0]}": "…", "{needed[1]}": "…"}}}}.')
        return fn(argument)
    except TypeError as e:
        needed = _required_params(fn)
        hint = f" It expects: {', '.join(needed)}." if needed else ""
        return f"Tool error: {name} was called with the wrong arguments ({e}).{hint}"
    except Exception as e:  # a bad tool call shouldn't kill the whole run
        return f"Tool error: {e}"


def _result(answer, finished, path_field, tool_calls, steps, started, max_steps, usage, history) -> AgentResult:
    return AgentResult(
        answer=answer,
        finished=finished,
        path_field=path_field,
        tool_calls=tool_calls,
        steps=steps,
        elapsed_seconds=time.perf_counter() - started,
        max_steps=max_steps,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        cost_usd=usage["cost_usd"],
        transcript=history,
    )


def _parse_json(text: str):
    """Parse a JSON *object*, tolerating prose or ```json code fences around it.

    Returns the parsed dict, or None if the text has no usable JSON object. Only
    objects are accepted: a bare JSON string/list/number is not a valid action
    and returning it would make the caller's ``action.get(...)`` raise.
    """
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    return None


def _as_str_list(v):
    return [str(x) for x in v] if isinstance(v, list) else None
