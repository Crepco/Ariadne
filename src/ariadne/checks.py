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
from ariadne.inference import reverse_reachable
from ariadne.schema import BASE_LABEL, CONTROL_EDGES_ANY, GOAL_GROUP


# Cap on rows returned by the graph-query checks. Without it, a check like
# `dangerous_acls` on a real domain can return tens of thousands of rows.
FINDING_LIMIT = 200


@dataclass
class Finding:
    check: str                       # which check produced it
    subject: str                     # the principal/object at issue (name)
    detail: str                      # one-line human summary
    severity: str = "medium"         # low | medium | high | critical
    evidence: list[str] = field(default_factory=list)   # concrete graph facts


class FindingSet(list):
    """A list of findings that knows whether the query behind it was capped.

    Subclasses ``list`` so every existing caller (``len``, slicing, ``sorted``)
    keeps working, while ``truncated``/``total`` let the report say "showing 200
    of 4,812" instead of silently presenting a truncated audit as complete.
    """

    def __init__(self, findings=(), *, total: int | None = None):
        super().__init__(findings)
        self.total = len(self) if total is None else total

    @property
    def truncated(self) -> bool:
        return self.total > len(self)


def _name(ctx, oid: str) -> str:
    return ctx.names.get(oid, oid)


def _count(ctx, query: str, params: dict) -> int:
    """Total matches for a capped query, so the report can report the cap honestly."""
    rows = run_read(ctx.driver, query, database=ctx.database, **params)
    return rows[0]["c"] if rows else 0


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def kerberoastable_to_da(ctx) -> list[Finding]:
    """Crackable service accounts (or the hosts exposing them) with a real path to DA."""
    # One backward BFS answers "does this reach DA?" for every candidate at once,
    # instead of a forward traversal per account.
    distance = reverse_reachable(ctx.canonical_adj, ctx.props, ctx.goal_oid)
    findings: list[Finding] = []
    for oid, p in ctx.props.items():
        if not (p.get("hasspn") and p.get("crackable")):
            continue
        hops = distance.get(oid)
        if hops is not None:
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
    match = (
        "MATCH (p)-[r]->(t) WHERE type(r) IN $edges AND "
        "(coalesce(t.highvalue,false) OR coalesce(t.admincount,false) OR t.objectid=$goal) "
    )
    params = {"edges": control, "goal": ctx.goal_oid}
    rows = run_read(
        ctx.driver,
        match + f"RETURN p.name AS principal, type(r) AS right, t.name AS target LIMIT {FINDING_LIMIT}",
        database=ctx.database, **params,
    )
    total = _count(ctx, match + "RETURN count(*) AS c", params) if len(rows) == FINDING_LIMIT else len(rows)
    return FindingSet((
        Finding(
            "dangerous_acls", r["principal"] or "?",
            f"{r['principal']} has {r['right']} over high-value {r['target']}.",
            "high", [f"{r['principal']} -[{r['right']}]-> {r['target']}"],
        )
        for r in rows
    ), total=total)


def nested_da(ctx) -> list[Finding]:
    """Groups that are non-obvious (transitive) members of Domain Admins."""
    if not ctx.goal_oid:
        return FindingSet()
    rows = run_read(
        ctx.driver,
        f"MATCH p=(g:Group)-[:MemberOf*2..]->(da:{BASE_LABEL} {{objectid:$goal}}) "
        f"RETURN g.name AS grp, min(length(p)) AS depth LIMIT {FINDING_LIMIT}",
        database=ctx.database,
        goal=ctx.goal_oid,
    )
    return FindingSet(
        Finding(
            "nested_da", r["grp"] or "?",
            f"{r['grp']} is a member of {GOAL_GROUP} through {r['depth']} levels of nesting.",
            "medium", [f"{r['grp']} -[MemberOf*{r['depth']}]-> {GOAL_GROUP}"],
        )
        for r in rows
    )


def session_exposure(ctx) -> list[Finding]:
    """Privileged (admincount) accounts with live sessions exposed on computers."""
    match = "MATCH (c:Computer)-[:HasSession]->(u:User) WHERE coalesce(u.admincount,false) "
    rows = run_read(
        ctx.driver,
        match + f"RETURN c.name AS host, u.name AS user LIMIT {FINDING_LIMIT}",
        database=ctx.database,
    )
    total = _count(ctx, match + "RETURN count(*) AS c", {}) if len(rows) == FINDING_LIMIT else len(rows)
    return FindingSet((
        Finding(
            "session_exposure", r["user"] or "?",
            f"Privileged account {r['user']} has a session on {r['host']} — credentials "
            f"are stealable by anyone who compromises that host.",
            "high", [f"{r['host']} -[HasSession]-> {r['user']} (admincount)"],
        )
        for r in rows
    ), total=total)


def adcs_esc1(ctx) -> list[Finding]:
    """Hosts with a misconfigured ADCS certificate template (ESC1 -> forge any cert)."""
    findings = []
    for oid, p in ctx.props.items():
        if p.get("esc1"):
            name = _name(ctx, oid)
            findings.append(Finding(
                "adcs_esc1", name,
                f"Misconfigured certificate template (ESC1) on {name} — an enrollee can "
                f"forge a certificate for any principal and reach {GOAL_GROUP}.",
                "critical", [f"{name}: esc1=true"],
            ))
    return findings


def credential_exposure(ctx) -> list[Finding]:
    """Hosts/GPOs leaking an account's plaintext credentials (description, GPP cpassword)."""
    findings = []
    for oid, p in ctx.props.items():
        target = p.get("cred_target")
        if target:
            name, acct = _name(ctx, oid), _name(ctx, target)
            findings.append(Finding(
                "credential_exposure", name,
                f"{name} exposes {acct}'s plaintext credentials — reach the host, read "
                f"the secret, and become {acct}.",
                "high", [f"{name}: cred_target -> {acct}"],
            ))
    return findings


CHECKS = {
    "kerberoastable_to_da": (kerberoastable_to_da, "Crackable service accounts with a real path to Domain Admins."),
    "unconstrained_delegation": (unconstrained_delegation, "Non-DC hosts trusted for unconstrained delegation."),
    "adcs_esc1": (adcs_esc1, "Misconfigured ADCS certificate templates (ESC1)."),
    "credential_exposure": (credential_exposure, "Hosts/GPOs leaking an account's plaintext credentials."),
    "dangerous_acls": (dangerous_acls, "Full-control ACLs over high-value / Tier-Zero objects."),
    "nested_da": (nested_da, "Non-obvious transitive membership in Domain Admins."),
    "session_exposure": (session_exposure, "Privileged sessions stealable from compromised hosts."),
}


def _as_set(findings) -> FindingSet:
    """Normalise a check's return value so every caller can read ``.truncated``.

    The property-scan checks iterate an in-memory map and are never capped, so
    they return plain lists; the graph-query checks return a FindingSet already.
    """
    return findings if isinstance(findings, FindingSet) else FindingSet(findings)


def run_check(name: str, ctx) -> FindingSet:
    if name not in CHECKS:
        raise KeyError(f"Unknown check {name!r}. Available: {', '.join(CHECKS)}")
    return _as_set(CHECKS[name][0](ctx))


def run_all(ctx) -> dict[str, FindingSet]:
    return {name: _as_set(fn(ctx)) for name, (fn, _desc) in CHECKS.items()}
