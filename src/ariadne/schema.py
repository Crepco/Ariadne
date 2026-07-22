"""The BloodHound-flavoured graph schema.

This is the shared vocabulary — node labels, relationship (edge) types, and the
subset of edges that count as an *attack path* — used by the generator, the
agent's query tools, and the ground-truth scoring. Keeping it in one place means
the agent, the data, and the answer key can never drift out of sync.

The schema mirrors the legacy BloodHound data model closely enough that a graph
built from it is structurally indistinguishable from a real SharpHound collection
for attack-path reasoning purposes.

**Edges vs. inference.** The graph — synthetic or ingested from a real BloodHound
export — contains only ``CANONICAL_EDGES``: the primitives BloodHound's classic
*"shortest path to Domain Admins"* Cypher query traverses. That query is the
rule-based baseline.

Advanced tradecraft (Kerberoasting a service account and cracking it offline;
abusing unconstrained delegation) is deliberately **not** modelled as edges. It is
derived from node **properties** (``hasspn`` + ``crackable``,
``unconstraineddelegation``) by inference rules (see ``ariadne.inference``). Those
steps are never written to Neo4j, so a pure edge-traversal query *structurally
cannot* find them, while a reasoner can — and every inferred step is machine-
checkable, so the agent can't fabricate one. That asymmetry is a property of the
data model, not a filter choice, which is what makes it an honest comparison.
"""

from __future__ import annotations

# --- Node labels -----------------------------------------------------------
NODE_LABELS = ["Domain", "User", "Group", "Computer"]

# --- Canonical relationship (edge) types ----------------------------------
# Membership / structure
MEMBERSHIP_EDGES = ["MemberOf"]

# Local admin / remote execution (principal -> Computer)
EXECUTION_EDGES = ["AdminTo", "CanRDP", "CanPSRemote", "ExecuteDCOM"]

# Credential exposure (Computer -> User: a privileged session to steal)
SESSION_EDGES = ["HasSession"]

# ACL / control primitives valid against *any* object (principal -> object)
CONTROL_EDGES_ANY = ["GenericAll", "GenericWrite", "WriteDacl", "WriteOwner", "Owns"]
# Control primitives that only make sense against a User
CONTROL_EDGES_USER = ["ForceChangePassword", "AllExtendedRights"]
# Control primitives that only make sense against a Group
CONTROL_EDGES_GROUP = ["AddMember", "AllExtendedRights"]

# Domain-dominance (principal -> Domain)
DOMAIN_EDGES = ["DCSync"]

# The set of edge types BloodHound's canonical shortest-path query follows — the
# rule-based baseline. THIS is the "BloodHound-equivalent" traversal definition.
CANONICAL_EDGES = sorted(
    set(
        MEMBERSHIP_EDGES
        + EXECUTION_EDGES
        + SESSION_EDGES
        + CONTROL_EDGES_ANY
        + CONTROL_EDGES_USER
        + CONTROL_EDGES_GROUP
        + DOMAIN_EDGES
    )
)

# The graph only ever contains canonical edges. ``TRAVERSABLE_EDGES`` is kept as
# an alias (= canonical) for call sites that ask "what edge types can appear in
# the graph"; advanced tradecraft is NOT here — it lives in ariadne.inference as
# property-based rules, never as edges.
TRAVERSABLE_EDGES = list(CANONICAL_EDGES)
ALL_EDGE_TYPES = list(CANONICAL_EDGES)

# --- Node properties that drive inference rules ---------------------------
# Advanced steps are derived from these properties (see ariadne.inference), not
# from edges, so a canonical edge-traversal query cannot express them.
#   hasspn                    User has a Service Principal Name -> kerberoastable.
#   crackable                 The SPN account's password is weak enough to crack
#                             offline (gates which kerberoastable accounts pivot).
#   roastable_target          On a host Computer: object id of a crackable service
#                             account it exposes. Reaching the host lets you roast
#                             that account -> a LOCAL inferred step (not an edge).
#   unconstraineddelegation   Computer trusted for unconstrained delegation ->
#                             coerce a privileged login and reuse its ticket.
INFERENCE_PROPERTIES = [
    "hasspn", "crackable", "roastable_target",   # kerberoast (host exposes crackable SPN)
    "unconstraineddelegation",                   # coerce + impersonate
    "cred_target",                               # host/GPO exposes an account's creds
    "esc1",                                      # misconfigured ADCS template (ESC1)
]

# --- Well-known groups -----------------------------------------------------
# RID -> display name, following real AD relative identifiers.
WELL_KNOWN_GROUPS = {
    512: "DOMAIN ADMINS",
    513: "DOMAIN USERS",
    516: "DOMAIN CONTROLLERS",
    519: "ENTERPRISE ADMINS",
    544: "ADMINISTRATORS",
}

# Groups that represent total or near-total domain control ("high value").
HIGH_VALUE_GROUPS = {"DOMAIN ADMINS", "ENTERPRISE ADMINS", "ADMINISTRATORS"}

# The escalation target for a run: membership in / control over this group.
GOAL_GROUP = "DOMAIN ADMINS"


def _rel_filter(edges) -> str:
    return "|".join(edges)


def canonical_rel_filter() -> str:
    """Return the ``A|B|C`` filter over CANONICAL edges (the graph's only edges).

    Used to build ``shortestPath((s)-[:<filter>*1..N]->(g))`` for the BloodHound
    baseline. Advanced steps are handled separately by ``ariadne.inference``.
    """
    return _rel_filter(CANONICAL_EDGES)


# Back-compat alias: the graph contains only canonical edges, so the two are equal.
cypher_rel_filter = canonical_rel_filter
