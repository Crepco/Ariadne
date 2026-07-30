"""The hop-by-hop path walk — one implementation, two presentations.

Verifying a proposed path means the same thing everywhere in Ariadne: resolve
each token to a node, then check every consecutive pair is a real canonical
**edge** or a property-**inferred** step (``inference.classify_hop``), and that
the last node is Domain Admins.

That walk used to be written twice — ``tools.verify_path`` (what the agent calls
before finishing) and ``score.verify_path`` (what decides whether the run counts
as correct) — with different return shapes and subtly different resolution. Two
implementations of the same rule is exactly how the project's central promise
("a path the tool calls valid is the path that will score as correct") quietly
becomes false.

So the walk lives here once. :func:`verify_walk` produces the full record the
scorer needs; :func:`as_tool_result` renders the same record into the terser,
instructional shape the agent sees.
"""

from __future__ import annotations

from ariadne.schema import GOAL_GROUP


def verify_walk(
    tokens: list[str],
    resolved: list[str | None],
    *,
    hop_kind,
    goal_oid: str | None,
    unknown: list[str] | None = None,
    ambiguous: list[str] | None = None,
    expected_start_oid: str | None = None,
) -> dict:
    """Walk an ordered path and return the canonical verification record.

    ``resolved`` is aligned with ``tokens`` (``None`` where a token didn't
    resolve). ``hop_kind(a, b)`` returns ``("edge", type)``, ``("inferred", rule)``
    or ``None``. Resolution itself is the caller's job because the two call sites
    fetch nodes differently (the scorer holds the whole graph in memory; the tool
    looks up only the path), but the *rules* below are shared.
    """
    unknown = list(unknown if unknown is not None else
                   [t for t, o in zip(tokens, resolved) if o is None])
    ambiguous = list(ambiguous or [])

    hop_edges: list[dict] = []
    derived_steps = 0
    first_bad: int | None = None
    connected = len(tokens) >= 2 and not unknown and not ambiguous

    if connected:
        for i, (a, b) in enumerate(zip(resolved, resolved[1:])):
            kind = hop_kind(a, b)
            inferred = bool(kind) and kind[0] == "inferred"
            hop_edges.append({
                "from": a, "to": b,
                "from_token": tokens[i], "to_token": tokens[i + 1],
                "edge": kind[1] if kind else None,
                "inferred": inferred,
            })
            if kind is None:
                connected = False
                if first_bad is None:
                    first_bad = i
            elif inferred:
                derived_steps += 1

    reaches_goal = bool(resolved) and resolved[-1] is not None and resolved[-1] == goal_oid
    starts_ok = expected_start_oid is None or (bool(resolved) and resolved[0] == expected_start_oid)
    valid = connected and reaches_goal and len(tokens) >= 2 and not unknown and not ambiguous
    # An unresolved node or a hop that is neither edge nor inference is the agent
    # asserting something the graph doesn't contain. An *ambiguous* name is not:
    # the node may well exist, the agent just didn't say which one.
    hallucinated = bool(unknown) or any(h["edge"] is None for h in hop_edges)

    return {
        "valid": valid,
        "hallucinated": hallucinated,
        "hops": (len(tokens) - 1) if len(tokens) >= 2 else -1,
        "reaches_goal": reaches_goal,
        "starts_ok": starts_ok,
        "unresolved": unknown,
        "ambiguous": ambiguous,
        "hop_edges": hop_edges,
        "derived_steps": derived_steps,
        "uses_derived": derived_steps > 0,
        "first_bad_hop": first_bad,
    }


def as_tool_result(record: dict) -> dict:
    """Render a walk record into the agent-facing result.

    The agent needs one thing the scorer doesn't: *what to do about it*. So this
    names the FIRST broken hop and says how to repair it, which is what turns a
    rejection into a corrected path rather than a give-up.
    """
    out = {
        "valid": record["valid"],
        "hops": [
            {"from": h["from_token"], "to": h["to_token"],
             "step": h["edge"], "valid": h["edge"] is not None}
            for h in record["hop_edges"]
        ],
        "derived_steps": record["derived_steps"],
        "reaches_goal": record["reaches_goal"],
    }

    if record["ambiguous"]:
        out["ambiguous"] = record["ambiguous"]
        out["reason"] = " ".join(record["ambiguous"])
        return out

    if record["unresolved"]:
        out["unresolved"] = record["unresolved"]
        out["reason"] = (
            f"These names do not exist in the graph: {', '.join(record['unresolved'])}. "
            f"Use exact names returned by search_node."
        )
        return out

    bad = record["first_bad_hop"]
    if bad is not None:
        hop = record["hop_edges"][bad]
        out["reason"] = (
            f"Hop {hop['from_token']} -> {hop['to_token']} is NOT a real step (no canonical "
            f"edge and no inferred rule justifies it). You likely skipped a node between "
            f"them — re-check {hop['from_token']}'s outbound edges and properties."
        )
    elif not record["reaches_goal"]:
        out["reason"] = (
            f"The path does not end at {GOAL_GROUP}; the last node must be DOMAIN ADMINS."
        )
    return out
