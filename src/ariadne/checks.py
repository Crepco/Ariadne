"""Vulnerability-check catalog — deterministic detections over the graph.

Each check is a plain function ``(ScoringContext) -> list[Finding]`` that queries
the graph (and the inference oracle) and returns findings backed by concrete graph
evidence. Because they are deterministic and evidence-linked, they *cannot*
hallucinate — they are the trustworthy core the chat assistant answers from. The
LLM's job on top is only to route questions to a check and summarise the findings,
never to invent them.

``CHECKS`` maps a name -> ``(function, description)``; ``run_check`` / ``run_all``
execute them against a loaded ``ScoringContext``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ariadne.db import run_read
from ariadne.inference import true_reachable
from ariadne.schema import CONTROL_EDGES_ANY, GOAL_GROUP


@dataclass
class Finding:
    check: str                       # which check produced it
    subject: str                     # the principal/object at issue (name)
    detail: str                      # one-line human summary
    severity: str = "medium"         # low | medium | high | critical
    evidence: list[str] = field(default_factory=list)   # concrete graph facts


def _name(ctx, oid: str) -> str:
    return ctx.names.get(oid, oid)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def kerberoastable_to_da(ctx) -> list[Finding]:
    """Crackable service accounts (or the hosts exposing them) with a real path to DA."""
    findings: list[Finding] = []
    for oid, p in ctx.props.items():
        if not (p.get("hasspn") and p.get("crackable")):
            continue
        reachable, hops = true_reachable(ctx.canonical_adj, ctx.props, oid, ctx.goal_oid)
        if reachable:
            name = _name(ctx, oid)
            findings.append(Finding(
                "kerberoastable_to_da", name,
                f"Kerberoastable service account with a crackable password reaches "
                f"{GOAL_GROUP} in ~{hops} hop(s) once compromised.",
                "high", [f"{name}: hasspn=true, crackable=true", f"reaches {GOAL_GROUP} ({hops} hops)"],
            ))
    return findings


def unconstrained_delegation(ctx) -> list[Finding]:
    """Non-DC computers trusted for unconstrained delegation (coerce -> dominance)."""
    findings = []
    for oid, p in ctx.props.items():
        if p.get("unconstraineddelegation") and not p.get("is_dc"):
            name = _name(ctx, oid)
            findings.append(Finding(
                "unconstrained_delegation", name,
                f"Non-DC host trusted for unconstrained delegation — coerce a privileged "
                f"login and reuse its ticket to reach {GOAL_GROUP}.",
                "critical", [f"{name}: unconstraineddelegation=true, is_dc=false"],
            ))
    return findings


def dangerous_acls(ctx) -> list[Finding]:
    """Principals with full-control ACLs (GenericAll/WriteDacl/WriteOwner/Owns) over a
    high-value / Tier-Zero object."""
    control = [e for e in CONTROL_EDGES_ANY]  # GenericAll, GenericWrite, WriteDacl, WriteOwner, Owns
    rows = run_read(
        ctx.driver,
        "MATCH (p)-[r]->(t) WHERE type(r) IN $edges AND "
        "(coalesce(t.highvalue,false) OR coalesce(t.admincount,false) OR t.objectid=$goal) "
        "RETURN p.name AS principal, type(r) AS right, t.name AS target LIMIT 200",
        database=ctx.database,
        edges=control,
        goal=ctx.goal_oid,
    )
    return [
        Finding(
            "dangerous_acls", r["principal"] or "?",
            f"{r['principal']} has {r['right']} over high-value {r['target']}.",
            "high", [f"{r['principal']} -[{r['right']}]-> {r['target']}"],
        )
        for r in rows
    ]


def nested_da(ctx) -> list[Finding]:
    """Groups that are non-obvious (transitive) members of Domain Admins."""
    if not ctx.goal_oid:
        return []
    rows = run_read(
        ctx.driver,
        "MATCH p=(g:Group)-[:MemberOf*2..]->(da {objectid:$goal}) "
        "RETURN g.name AS grp, min(length(p)) AS depth LIMIT 200",
        database=ctx.database,
        goal=ctx.goal_oid,
    )
    return [
        Finding(
            "nested_da", r["grp"] or "?",
            f"{r['grp']} is a member of {GOAL_GROUP} through {r['depth']} levels of nesting.",
            "medium", [f"{r['grp']} -[MemberOf*{r['depth']}]-> {GOAL_GROUP}"],
        )
        for r in rows
    ]


def session_exposure(ctx) -> list[Finding]:
    """Privileged (admincount) accounts with live sessions exposed on computers."""
    rows = run_read(
        ctx.driver,
        "MATCH (c:Computer)-[:HasSession]->(u:User) WHERE coalesce(u.admincount,false) "
        "RETURN c.name AS host, u.name AS user LIMIT 200",
        database=ctx.database,
    )
    return [
        Finding(
            "session_exposure", r["user"] or "?",
            f"Privileged account {r['user']} has a session on {r['host']} — credentials "
            f"are stealable by anyone who compromises that host.",
            "high", [f"{r['host']} -[HasSession]-> {r['user']} (admincount)"],
        )
        for r in rows
    ]


CHECKS = {
    "kerberoastable_to_da": (kerberoastable_to_da, "Crackable service accounts with a real path to Domain Admins."),
    "unconstrained_delegation": (unconstrained_delegation, "Non-DC hosts trusted for unconstrained delegation."),
    "dangerous_acls": (dangerous_acls, "Full-control ACLs over high-value / Tier-Zero objects."),
    "nested_da": (nested_da, "Non-obvious transitive membership in Domain Admins."),
    "session_exposure": (session_exposure, "Privileged sessions stealable from compromised hosts."),
}


def run_check(name: str, ctx) -> list[Finding]:
    if name not in CHECKS:
        raise KeyError(f"Unknown check {name!r}. Available: {', '.join(CHECKS)}")
    return CHECKS[name][0](ctx)


def run_all(ctx) -> dict[str, list[Finding]]:
    return {name: fn(ctx) for name, (fn, _desc) in CHECKS.items()}
