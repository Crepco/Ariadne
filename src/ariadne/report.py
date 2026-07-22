"""Reader outputs shared by the benchmark and the chat assistant.

* ``explain_path`` — turn a *verified* path into a plain-English attack narrative
  plus remediation. It first re-verifies the path against the graph, then asks the
  LLM to narrate only the steps that checked out (each tagged edge vs. inferred),
  so the explanation is grounded and cannot invent a hop.
* ``rank_paths`` — a deterministic triage proxy: score paths by how close they get
  to high-value targets and how short they are. No LLM, so it never hallucinates a
  ranking; it is the substance the assistant presents.
* ``domain_report`` — a whole-domain audit as markdown: the vulnerability checks
  plus the "paths BloodHound can't see" summary. Fully deterministic (no LLM), so
  it is reproducible and cannot fabricate a finding.
"""

from __future__ import annotations

from ariadne.agent.llm import chat
from ariadne.checks import CHECKS, run_all
from ariadne.db import run_read
from ariadne.evaluation.score import verify_path
from ariadne.inference import true_reachable
from ariadne.schema import GOAL_GROUP


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


# ---------------------------------------------------------------------------
# Whole-domain audit report (deterministic markdown)
# ---------------------------------------------------------------------------
_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Checks whose findings are INFERRED tradecraft — property-derived steps a
# canonical shortest-path query structurally cannot follow (the "beats BloodHound"
# surface). Maps check name -> the short tradecraft label used in the report.
_INFERRED_CHECKS = {
    "kerberoastable_to_da": "Kerberoast (crack a service ticket offline)",
    "adcs_esc1": "ADCS ESC1 (forge a certificate)",
    "credential_exposure": "Credential exposure (read a leaked secret)",
    "unconstrained_delegation": "Unconstrained delegation (coerce + impersonate)",
}

# One remediation line per check type (deterministic — no LLM).
_REMEDIATION = {
    "kerberoastable_to_da": "Give service accounts long, random (gMSA) passwords and strip needless SPNs.",
    "unconstrained_delegation": "Remove unconstrained delegation; use constrained/RBCD and mark Tier-0 accounts sensitive.",
    "adcs_esc1": "Fix the certificate template: disable requester-supplied SANs and require manager approval.",
    "credential_exposure": "Purge plaintext secrets from descriptions/GPP; rotate any exposed credentials.",
    "dangerous_acls": "Remove full-control ACLs over Tier-0 objects; restrict to a reviewed admin tier.",
    "nested_da": "Flatten group nesting into Domain Admins; audit every transitive member.",
    "session_exposure": "Keep privileged logons off member hosts; enforce credential isolation (LSA/Credential Guard).",
}


def _counts_by_label(ctx) -> tuple[dict[str, int], int]:
    rows = run_read(
        ctx.driver,
        "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c ORDER BY c DESC",
        database=ctx.database,
    )
    counts = {r["label"]: r["c"] for r in rows}
    erows = run_read(ctx.driver, "MATCH ()-[r]->() RETURN count(r) AS c", database=ctx.database)
    edge_count = erows[0]["c"] if erows else 0
    return counts, edge_count


def _foothold_stats(ctx) -> tuple[int, int, int]:
    """(users that reach DA, of those how many ONLY via an inferred step, total users).

    Canonical-only reachability uses an empty property map so no inference fires —
    exactly the BloodHound baseline. TRUE reachability adds the inference oracle."""
    rows = run_read(ctx.driver, "MATCH (u:User) RETURN u.objectid AS oid", database=ctx.database)
    users = [r["oid"] for r in rows]
    reach = advanced_only = 0
    for oid in users:
        true_ok, _ = true_reachable(ctx.canonical_adj, ctx.props, oid, ctx.goal_oid)
        if not true_ok:
            continue
        reach += 1
        canon_ok, _ = true_reachable(ctx.canonical_adj, {}, oid, ctx.goal_oid)
        if not canon_ok:
            advanced_only += 1
    return reach, advanced_only, len(users)


def domain_report(ctx) -> str:
    """A whole-domain audit as markdown: every deterministic check plus the
    "paths BloodHound can't see" summary. No LLM — reproducible and unfabricatable."""
    domain = next((n.split("@")[-1] for n in ctx.names.values() if "@" in n), "the domain")

    counts, edge_count = _counts_by_label(ctx)
    all_findings = run_all(ctx)
    flat = [f for fs in all_findings.values() for f in fs]
    by_sev: dict[str, int] = {}
    for f in flat:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
    reach, advanced_only, n_users = _foothold_stats(ctx)

    L: list[str] = []
    L.append(f"# Ariadne domain audit — {domain}")
    L.append("")
    L.append("_Deterministic, evidence-backed audit. **Inferred** steps below are derived "
             "from node properties, not edges, so BloodHound's canonical shortest-path "
             "query structurally cannot follow them._")
    L.append("")

    # -- Summary --
    L.append("## Summary")
    L.append("")
    obj_total = sum(counts.values())
    obj_break = ", ".join(f"{k} {v}" for k, v in counts.items())
    L.append(f"- **Objects:** {obj_total} ({obj_break})")
    L.append(f"- **Canonical edges:** {edge_count}")
    sev_break = ", ".join(f"{by_sev.get(s, 0)} {s}" for s in ("critical", "high", "medium", "low")
                          if by_sev.get(s))
    L.append(f"- **Findings:** {len(flat)} total" + (f" — {sev_break}" if sev_break else ""))
    L.append(f"- **Escalation footholds:** {reach}/{n_users} users can reach {GOAL_GROUP}; "
             f"of those, **{advanced_only} are reachable ONLY through inferred tradecraft** "
             f"(invisible to BloodHound's canonical query).")
    L.append("")

    # -- Findings by check, most-severe checks first --
    L.append("## Findings by check")
    L.append("")
    ordered = sorted(
        CHECKS,
        key=lambda name: (min((_SEV_RANK.get(f.severity, 9) for f in all_findings.get(name, [])), default=9),
                          -len(all_findings.get(name, []))),
    )
    for name in ordered:
        findings = all_findings.get(name, [])
        desc = CHECKS[name][1]
        tag = " _(inferred — BloodHound-blind)_" if name in _INFERRED_CHECKS else ""
        L.append(f"### {name.replace('_', ' ')} — {len(findings)} finding(s){tag}")
        L.append(f"_{desc}_")
        if not findings:
            L.append("")
            L.append("- None found.")
            L.append("")
            continue
        L.append("")
        for f in sorted(findings, key=lambda f: _SEV_RANK.get(f.severity, 9))[:25]:
            subj = (f.subject or "?").split("@")[0]
            L.append(f"- **[{f.severity}] {subj}** — {f.detail}")
            for ev in f.evidence:
                L.append(f"  - `{ev}`")
        if len(findings) > 25:
            L.append(f"  - …and {len(findings) - 25} more.")
        L.append("")

    # -- The headline: paths BloodHound can't see --
    L.append("## Paths BloodHound can't see")
    L.append("")
    inferred_hits = {name: len(all_findings.get(name, [])) for name in _INFERRED_CHECKS
                     if all_findings.get(name)}
    if inferred_hits:
        L.append("These footholds escalate through a property-derived step with no edge "
                 "equivalent, so a canonical shortest-path query misses them entirely:")
        L.append("")
        for name, n in inferred_hits.items():
            L.append(f"- **{_INFERRED_CHECKS[name]}** — {n} finding(s) (`{name}`)")
        L.append("")
    pct = f" ({advanced_only / reach:.0%} of all footholds)" if reach else ""
    L.append(f"**{advanced_only} user(s) reach {GOAL_GROUP} ONLY via one of these inferred "
             f"steps{pct}** — the concrete gap between a reasoning reader and a rule-based query.")
    L.append("")

    # -- Remediation --
    L.append("## Remediation")
    L.append("")
    for name in ordered:
        if all_findings.get(name) and name in _REMEDIATION:
            L.append(f"- **{name.replace('_', ' ')}:** {_REMEDIATION[name]}")
    L.append("")
    return "\n".join(L)


def main() -> None:
    import argparse
    from pathlib import Path

    from ariadne.evaluation.score import ScoringContext

    ap = argparse.ArgumentParser(description="Generate a whole-domain audit report (markdown).")
    ap.add_argument("-o", "--out", help="write the report to this file (default: stdout)")
    args = ap.parse_args()

    ctx = ScoringContext.load()
    md = domain_report(ctx)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"Wrote report -> {args.out}")
    else:
        print(md)


if __name__ == "__main__":
    main()
