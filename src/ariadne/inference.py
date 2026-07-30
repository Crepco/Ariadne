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
* **CredentialExposure** — a host or GPO leaks an account's plaintext credentials
  (``cred_target`` points at that account): reach it, read the secret, become
  that account. Local for the same reason.
* **UnconstrainedDelegation** — a computer trusted for unconstrained delegation
  (``unconstraineddelegation``) lets an attacker who reaches it coerce a
  privileged login and reuse that ticket for domain dominance.
* **ADCS_ESC1** — a misconfigured certificate template (``esc1``) lets the
  enrollee supply an arbitrary subject, so reaching it means forging a
  certificate for any principal.

The last two are *dominance* rules: they are only accepted when the destination
is the goal itself, so neither can be used as a free jump to an arbitrary node.

These steps are never written to Neo4j, so a pure edge-traversal query
*structurally* cannot find them, while this oracle (and a reasoning agent) can.
Every inferred step is decidable from properties, so the agent cannot fabricate
one and pass verification.

Entry points:

* ``justifies_hop(props, a, b, goal)`` — does an inference rule make the single
  step ``a -> b`` valid? Used by the hop-by-hop verifier alongside the canonical
  edge check.
* ``true_reachable(adjacency, props, start, goal)`` — shortest path over canonical
  edges PLUS local inferred jumps, for ONE start. This is the TRUE ground truth
  the agent is scored against; the BloodHound baseline is the canonical-only
  version (call it with ``props={}``, since no rule can fire without properties).
* ``reverse_reachable(adjacency, props, goal)`` — the same oracle answered for
  every node at once, via a single backward BFS. Use this instead of looping
  ``true_reachable`` over candidates: the loop is O(V·(V+E)) and does not finish
  on a real domain.
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
    "CredentialExposure": (
        "A host or GPO exposes an account's plaintext credentials (a password left "
        "in a description, or a GPP cpassword in SYSVOL); reach it, read the secret, "
        "and become that account."
    ),
    "ADCS_ESC1": (
        "Enrol in a misconfigured certificate template (ESC1: it lets the enrollee "
        "supply an arbitrary subject) to forge a certificate for any principal and "
        "reach domain dominance."
    ),
}


def _props(props: dict, oid: str) -> dict:
    return props.get(oid) or {}


def justifies_hop(props: dict, a_oid: str, b_oid: str, goal_oid: str | None) -> str | None:
    """Return the inference rule that makes ``a_oid -> b_oid`` a valid step, or None.

    Canonical edges are checked separately by the caller; this only answers the
    *inferred* case. Every rule is gated on a property of the SOURCE node ``a``
    (so the step is local — you had to reach ``a`` to take it), and the two
    dominance rules additionally require ``b`` to BE the goal, so neither can be
    used as a free jump to an arbitrary node.
    """
    a = _props(props, a_oid)
    if a.get("roastable_target") and a.get("roastable_target") == b_oid:
        return "Kerberoast"
    if a.get("cred_target") and a.get("cred_target") == b_oid:
        return "CredentialExposure"
    if goal_oid is not None and b_oid == goal_oid and a.get("unconstraineddelegation"):
        return "UnconstrainedDelegation"
    if goal_oid is not None and b_oid == goal_oid and a.get("esc1"):
        return "ADCS_ESC1"
    return None


def classify_hop(edge_type: str | None, props: dict, a_oid: str, b_oid: str,
                 goal_oid: str | None) -> tuple[str, str] | None:
    """Classify a single step ``a -> b`` given the canonical edge type between them.

    Returns ``("edge", <type>)`` when a real canonical edge connects them,
    ``("inferred", <rule>)`` when a property justifies the step, or ``None`` when
    it is neither (a hallucination). This is the ONE place the edge-or-inference
    decision lives, so the scorer (``score.hop_kind``) and the agent's
    ``verify_path`` tool always agree.
    """
    if edge_type is not None:
        return ("edge", edge_type)
    rule = justifies_hop(props, a_oid, b_oid, goal_oid)
    if rule is not None:
        return ("inferred", rule)
    return None


def _inferred_jumps(props: dict, node: str, goal: str) -> list[str]:
    """Extra (non-edge) destinations reachable from ``node`` by an inference rule."""
    p = _props(props, node)
    out: list[str] = []
    tgt = p.get("roastable_target")
    if tgt:
        out.append(tgt)                    # kerberoast the exposed service account
    cred = p.get("cred_target")
    if cred:
        out.append(cred)                   # read exposed creds -> become that account
    if p.get("unconstraineddelegation"):
        out.append(goal)                   # unconstrained delegation -> dominance
    if p.get("esc1"):
        out.append(goal)                   # ADCS ESC1 -> forge cert -> dominance
    return out


def true_reachable(adjacency: dict, props: dict, start: str, goal: str) -> tuple[bool, int]:
    """Shortest path ``start -> goal`` over canonical edges PLUS local inferred jumps.

    Returns ``(reachable, hops)`` with ``hops == -1`` when unreachable. This is the
    TRUE reachability oracle for a *single* start; to ask "which of these many
    nodes reach the goal?", use :func:`reverse_reachable` instead of calling this
    in a loop.
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


def reverse_adjacency(adjacency: dict, props: dict, goal: str) -> dict[str, list[str]]:
    """Invert the traversal graph: ``node -> [predecessors]``.

    Includes the inferred (non-edge) jumps, so the result covers exactly the same
    steps :func:`true_reachable` would walk forward.
    """
    reverse: dict[str, list[str]] = {}
    nodes = set(adjacency) | set(props)
    for node in nodes:
        for successor in list(adjacency.get(node, ())) + _inferred_jumps(props, node, goal):
            reverse.setdefault(successor, []).append(node)
    return reverse


def reverse_reachable(adjacency: dict, props: dict, goal: str) -> dict[str, int]:
    """Every node that can reach ``goal``, mapped to its hop distance.

    One BFS *backwards* from the goal answers for the whole graph at once. The
    forward alternative — calling :func:`true_reachable` once per candidate — is
    O(V·(V+E)), which is fine on a 200-node synthetic graph and hopeless on a real
    domain with tens of thousands of users. Same answers, one traversal.

    ``goal`` itself maps to 0. Pass ``props={}`` to get canonical-only (BloodHound
    baseline) reachability, since no inference rule can fire without properties.
    """
    if goal is None:
        return {}
    reverse = reverse_adjacency(adjacency, props, goal)
    distances = {goal: 0}
    queue: deque[str] = deque([goal])
    while queue:
        node = queue.popleft()
        for predecessor in reverse.get(node, ()):
            if predecessor not in distances:
                distances[predecessor] = distances[node] + 1
                queue.append(predecessor)
    return distances
