"""Property-based inference rules — the advanced tradecraft a canonical
shortest-path query cannot express.

BloodHound's collected graph is made of edges. Some real escalation steps are not
edges at all — they must be *inferred* from node properties, and crucially they
are **local**: you can only take them once you have reached the right node.

* **Kerberoast** — a host computer exposes a service account with a crackable
  password (``roastable_target`` points at that account's object id). Once you
  reach the host, you can request that account's ticket and crack it offline,
  becoming the account. You must reach the *host* first — it is not a free jump
  from anywhere — which keeps it discriminating.
* **UnconstrainedDelegation** — a computer trusted for unconstrained delegation
  (``unconstraineddelegation``) lets an attacker who reaches it coerce a
  privileged login and reuse that ticket for domain dominance.

These steps are never written to Neo4j, so a pure edge-traversal query
*structurally* cannot find them, while this oracle (and a reasoning agent) can.
Every inferred step is decidable from properties, so the agent cannot fabricate
one and pass verification.

Entry points:

* ``justifies_hop(props, a, b, goal)`` — does an inference rule make the single
  step ``a -> b`` valid? Used by the hop-by-hop verifier alongside the canonical
  edge check.
* ``true_reachable(adjacency, props, start, goal)`` — shortest path over canonical
  edges PLUS local inferred jumps. This is the TRUE ground truth the agent is
  scored against; the BloodHound baseline is the canonical-only version.
"""

from __future__ import annotations

from collections import deque

# Rule name -> human-readable description (for prompts / reports / checks).
INFERENCE_RULES = {
    "Kerberoast": (
        "From a host that exposes a crackable service account (roastable_target), "
        "request its Kerberos ticket and crack it offline to become that account."
    ),
    "UnconstrainedDelegation": (
        "Coerce a privileged login to an unconstrained-delegation host and reuse "
        "its captured ticket to reach domain dominance."
    ),
}


def _props(props: dict, oid: str) -> dict:
    return props.get(oid) or {}


def justifies_hop(props: dict, a_oid: str, b_oid: str, goal_oid: str | None) -> str | None:
    """Return the inference rule that makes ``a_oid -> b_oid`` a valid step, or None.

    Canonical edges are checked separately by the caller; this only answers the
    *inferred* case, and both rules are gated on a property of the SOURCE node
    ``a`` (so the step is local — you had to reach ``a`` to take it).
    """
    a = _props(props, a_oid)
    if a.get("roastable_target") and a.get("roastable_target") == b_oid:
        return "Kerberoast"
    if goal_oid is not None and b_oid == goal_oid and a.get("unconstraineddelegation"):
        return "UnconstrainedDelegation"
    return None


def _inferred_jumps(props: dict, node: str, goal: str) -> list[str]:
    """Extra (non-edge) destinations reachable from ``node`` by an inference rule."""
    p = _props(props, node)
    out: list[str] = []
    tgt = p.get("roastable_target")
    if tgt:
        out.append(tgt)                    # kerberoast the exposed service account
    if p.get("unconstraineddelegation"):
        out.append(goal)                   # unconstrained delegation -> dominance
    return out


def true_reachable(adjacency: dict, props: dict, start: str, goal: str) -> tuple[bool, int]:
    """Shortest path ``start -> goal`` over canonical edges PLUS local inferred jumps.

    Returns ``(reachable, hops)`` with ``hops == -1`` when unreachable. This is the
    TRUE reachability oracle; run it on benchmark-scale graphs (for very large real
    BloodHound graphs, sample starts — see the ingest docs).
    """
    if start == goal:
        return True, 0
    seen = {start}
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    while queue:
        node, dist = queue.popleft()
        for m in list(adjacency.get(node, ())) + _inferred_jumps(props, node, goal):
            if m == goal:
                return True, dist + 1
            if m not in seen:
                seen.add(m)
                queue.append((m, dist + 1))
    return False, -1
