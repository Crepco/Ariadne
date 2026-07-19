"""The BloodHound-flavoured graph schema.

This is the shared vocabulary — node labels, relationship (edge) types, and the
subset of edges that count as an *attack path* — used by the generator, the
agent's query tools, and the ground-truth scoring. Keeping it in one place means
the agent, the data, and the answer key can never drift out of sync.

The schema mirrors the legacy BloodHound data model closely enough that a graph
built from it is structurally indistinguishable from a real SharpHound collection
for attack-path reasoning purposes.

**Canonical vs. advanced edges.** We split the attack-relevant edges into two
tiers:

* ``CANONICAL_EDGES`` — the primitives BloodHound's classic *"shortest path to
  Domain Admins"* Cypher query traverses. This is the rule-based baseline.
* ``ADVANCED_EDGES`` — tradecraft that a canonical shortest-path query does *not*
  encode but a reasoning agent can still chain: Kerberoasting a service account
  and cracking it offline, or abusing unconstrained delegation to coerce and
  impersonate. These are real edges in the graph; the agent's tools return them
  and hop-by-hop scoring accepts them, but the BloodHound-equivalent baseline
  ignores them.

The agent (and the "true reachability" ground truth) traverse
``TRAVERSABLE_EDGES = CANONICAL_EDGES + ADVANCED_EDGES``. The BloodHound baseline
traverses only ``CANONICAL_EDGES``. That asymmetry is what makes it possible for
the agent to find a *real* path the rule-based baseline misses.
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

# --- Advanced relationship (edge) types -----------------------------------
# Tradecraft the canonical shortest-path query does NOT encode, but a reasoning
# agent can chain. Real edges the agent may traverse and scoring accepts.
#   Kerberoastable            principal -> User(hasspn): request the SPN's
#                             service ticket and crack it offline to take over
#                             the service account.
#   UnconstrainedDelegationAbuse
#                             Computer(unconstrained) -> Group/Domain: coerce a
#                             privileged account to authenticate to the host and
#                             capture its TGT, escalating to domain dominance.
ADVANCED_EDGES = ["Kerberoastable", "UnconstrainedDelegationAbuse"]

# Everything the agent may traverse and hop-by-hop scoring will accept as a real
# attack primitive: the canonical set PLUS the advanced tradecraft.
TRAVERSABLE_EDGES = sorted(set(CANONICAL_EDGES + ADVANCED_EDGES))

# Every edge type that may appear in the database (identical to TRAVERSABLE here,
# but kept separate so non-traversable structural edges can be added later
# without widening the attack surface).
ALL_EDGE_TYPES = list(TRAVERSABLE_EDGES)

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


def cypher_rel_filter() -> str:
    """Return the ``A|B|C`` filter over ALL traversable edges (agent / true reach).

    Used to build ``shortestPath((s)-[:<filter>*1..N]->(g))`` so a traversal
    follows every attack-relevant edge — canonical and advanced — and nothing
    else.
    """
    return _rel_filter(TRAVERSABLE_EDGES)


def canonical_rel_filter() -> str:
    """Return the ``A|B|C`` filter over CANONICAL edges only (BloodHound baseline)."""
    return _rel_filter(CANONICAL_EDGES)
