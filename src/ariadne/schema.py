"""The BloodHound-flavoured graph schema.

This is the shared vocabulary — node labels, relationship (edge) types, and the
subset of edges that count as an *attack path* — used by the generator, the
agent's query tools, and the ground-truth scoring. Keeping it in one place means
the agent, the data, and the answer key can never drift out of sync.

The schema mirrors the legacy BloodHound data model closely enough that a graph
built from it is structurally indistinguishable from a real SharpHound collection
for attack-path reasoning purposes.
"""

from __future__ import annotations

# --- Node labels -----------------------------------------------------------
NODE_LABELS = ["Domain", "User", "Group", "Computer"]

# --- Relationship (edge) types --------------------------------------------
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

# The full set of edge types the agent is allowed to traverse when it reasons
# about escalation — and, crucially, the exact set the ground-truth shortest-path
# query follows. This IS the "BloodHound-equivalent" traversal definition.
TRAVERSABLE_EDGES = sorted(
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

# Every edge type that may appear in the database (identical here, but kept
# separate so non-traversable structural edges can be added later without
# widening the attack surface).
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


def cypher_rel_filter() -> str:
    """Return the ``A|B|C`` relationship-type filter for variable-length Cypher.

    Used to build ``shortestPath((s)-[:<filter>*1..N]->(g))`` so the ground-truth
    query traverses exactly the attack-relevant edges and nothing else.
    """
    return "|".join(TRAVERSABLE_EDGES)
