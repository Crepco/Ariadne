"""Reader outputs shared by the benchmark and the chat assistant.

* ``explain_path`` — turn a *verified* path into a plain-English attack narrative
  plus remediation. It first re-verifies the path against the graph, then asks the
  LLM to narrate only the steps that checked out (each tagged edge vs. inferred),
  so the explanation is grounded and cannot invent a hop.
* ``rank_paths`` — a deterministic triage proxy: score paths by how close they get
  to high-value targets and how short they are. No LLM, so it never hallucinates a
  ranking; it is the substance the assistant presents.
"""

from __future__ import annotations

from ariadne.agent.llm import chat
from ariadne.evaluation.score import verify_path


def _names(ctx, oids: list[str]) -> list[str]:
    return [ctx.names.get(o, o) for o in oids]


def explain_path(ctx, tokens: list[str]) -> str:
    """Narrate a verified attack path. Returns a grounded explanation, or a clear
    'could not verify' message if the path doesn't hold up against the graph."""
    v = verify_path(ctx, tokens)
    if not v["valid"]:
        bad = v["unresolved"] or [h for h in v["hop_edges"] if h["edge"] is None]
        return f"Could not verify this path against the graph (unresolved/invalid: {bad}). Not explaining an unverified path."

    steps = []
    for hop in v["hop_edges"]:
        frm, to = ctx.names.get(hop["from"], hop["from"]), ctx.names.get(hop["to"], hop["to"])
        kind = "INFERRED tradecraft" if hop["inferred"] else "edge"
        steps.append(f"{frm} --[{hop['edge']} ({kind})]--> {to}")
    step_block = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))

    prompt = f"""You are an Active Directory security analyst. Explain this VERIFIED
attack path to Domain Admins in plain English, then give concrete remediation for
each step. Do not add steps or claims beyond those listed — every step below was
checked against the graph.

Verified steps:
{step_block}

Write: (1) a short narrative of how an attacker walks this path, (2) a bullet list
of remediations, one per step."""
    return chat([{"role": "user", "content": prompt}]).text


def rank_paths(ctx, paths: list[list[str]]) -> list[dict]:
    """Deterministic triage: rank paths (each a list of object ids) by impact.

    Score rewards reaching high-value/admin/DC nodes and penalises length, so the
    most consequential, shortest paths surface first. No LLM — pure graph facts.
    """
    ranked = []
    for path in paths:
        hops = max(len(path) - 1, 0)
        value = 0
        hits = []
        for oid in path:
            p = ctx.props.get(oid) or {}
            if p.get("highvalue") or p.get("admincount") or p.get("is_dc"):
                value += 1
                hits.append(ctx.names.get(oid, oid))
        score = value * 10 - hops
        ranked.append({
            "path": _names(ctx, path),
            "hops": hops,
            "high_value_nodes": hits,
            "score": score,
            "reason": f"{value} high-value node(s) reached in {hops} hop(s)",
        })
    return sorted(ranked, key=lambda r: r["score"], reverse=True)
