"""Scoring for one agent run — and the verifier the whole project rests on.

Two things are measured:

1. **Is the agent's proposed path real?** We verify *each consecutive hop*: it must
   be either a real canonical **edge** in the graph OR a property-justified
   **inferred** step (``ariadne.inference``). A hop that is neither — or an
   unresolvable node — is a hallucination. ``hop_kind`` makes that call, and it is
   the same gate the chat assistant uses to refuse unverifiable claims.

2. **How does it compare to BloodHound?** ``baseline`` is TRUE reachability
   (canonical edges + inference); ``bloodhound`` is the canonical-only shortest
   path a rule-based query would find. When the agent's verified path uses an
   inferred step and the canonical query finds nothing, it ``beats_bloodhound`` —
   a structural fact, since inferred steps are not edges in the collected graph.

``score_run`` (simple reachability) is kept for backward compatibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ariadne.config import load_neo4j_config
from ariadne.db import get_driver, run_read
from ariadne.inference import INFERENCE_RULES, classify_hop, true_reachable
from ariadne.schema import CANONICAL_EDGES, GOAL_GROUP, INFERENCE_PROPERTIES
from ariadne.tools import check_path_exists

_ARROW = re.compile(r"->|=>|→")
# Tokens that are edge/rule labels, not nodes, so path parsing drops them.
_EDGE_SET = {e.upper() for e in CANONICAL_EDGES} | {r.upper() for r in INFERENCE_RULES}


# --------------------------------------------------------------------------
# Parse the agent's proposed path into an ordered list of node tokens
# --------------------------------------------------------------------------
def parse_path_tokens(answer: str, path_field=None) -> list[str]:
    """Extract the ordered NODE tokens the agent proposed.

    Prefers the explicit ``path`` list from the finish action; otherwise parses
    the free-text answer (``A -> Edge -> B -> ...``) and drops tokens that are
    edge types, leaving just the nodes.
    """
    if path_field:
        return [str(t).strip() for t in path_field if str(t).strip()]

    tokens = []
    for tok in _ARROW.split(answer or ""):
        clean = tok.strip().strip("=[]() ").strip()
        if not clean or clean.upper() in _EDGE_SET:
            continue
        tokens.append(clean)
    return tokens


# --------------------------------------------------------------------------
# Per-graph scoring context (built once per generated graph)
# --------------------------------------------------------------------------
@dataclass
class ScoringContext:
    driver: object
    database: str
    goal_oid: str | None
    name_to_oid: dict = field(default_factory=dict)
    names: dict = field(default_factory=dict)          # oid -> display name
    oids: set = field(default_factory=set)
    props: dict = field(default_factory=dict)          # oid -> inference properties
    canonical_adj: dict = field(default_factory=dict)  # oid -> [canonical successors]
    edge_types: dict = field(default_factory=dict)     # (a,b) -> canonical edge type
    canonical_filter: str = ""                          # canonical edges only (BloodHound)

    @classmethod
    def load(cls) -> "ScoringContext":
        database = load_neo4j_config().database
        driver = get_driver()

        name_to_oid: dict[str, str] = {}
        names: dict[str, str] = {}
        oids: set[str] = set()
        props: dict[str, dict] = {}
        prop_cols = ", ".join(f"n.{p} AS {p}" for p in INFERENCE_PROPERTIES)
        for row in run_read(
            driver,
            f"MATCH (n) RETURN n.objectid AS oid, n.name AS name, {prop_cols}",
            database=database,
        ):
            oid, name = row["oid"], row["name"]
            if not oid:
                continue
            oids.add(oid)
            props[oid] = {p: row.get(p) for p in INFERENCE_PROPERTIES}
            if name:
                names[oid] = name
                name_to_oid[name.upper()] = oid
                # short name too: users are USER@DOMAIN, computers are HOST.DOMAIN,
                # so split on either separator.
                name_to_oid[re.split(r"[@.]", name)[0].upper()] = oid

        goal_rows = run_read(
            driver,
            "MATCH (g:Group) WHERE g.name STARTS WITH $p RETURN g.objectid AS oid",
            database=database,
            p=f"{GOAL_GROUP}@",
        )
        goal_oid = goal_rows[0]["oid"] if goal_rows else None

        # Canonical edges: build adjacency + (a,b)->type once, and the present-type
        # filter for the BloodHound Cypher baseline.
        canonical_adj: dict[str, list[str]] = {}
        edge_types: dict[tuple[str, str], str] = {}
        present: set[str] = set()
        for row in run_read(
            driver,
            "MATCH (a)-[r]->(b) WHERE type(r) IN $canon "
            "RETURN a.objectid AS a, type(r) AS t, b.objectid AS b",
            database=database,
            canon=list(CANONICAL_EDGES),
        ):
            a, b, t = row["a"], row["b"], row["t"]
            canonical_adj.setdefault(a, []).append(b)
            edge_types[(a, b)] = t
            present.add(t)
        canonical_filter = "|".join(e for e in CANONICAL_EDGES if e in present)
        return cls(driver, database, goal_oid, name_to_oid, names, oids, props,
                   canonical_adj, edge_types, canonical_filter)

    def close(self) -> None:
        # The driver is the process-wide shared instance (ariadne.db), so we do
        # NOT close it here — other runs in the same sweep reuse it. It is closed
        # once at interpreter exit. Kept as a no-op for call-site compatibility.
        return None

    # -- resolution / graph checks --
    def resolve(self, token: str):
        t = (token or "").strip()
        if t in self.oids:
            return t
        return self.name_to_oid.get(t.upper())

    def hop_kind(self, a_oid: str, b_oid: str):
        """Classify the step a->b: ('edge', type) for a real canonical edge,
        ('inferred', rule) for a property-justified step, or None if neither
        (which the verifier counts as a hallucination)."""
        return classify_hop(self.edge_types.get((a_oid, b_oid)), self.props,
                             a_oid, b_oid, self.goal_oid)

    def baseline(self, start_oid: str) -> dict:
        """TRUE ground truth: shortest path over canonical edges PLUS property-
        inferred steps. This is what the agent is *actually* scored against."""
        reachable, hops = true_reachable(self.canonical_adj, self.props, start_oid, self.goal_oid)
        return {"reachable": reachable, "hops": hops}

    def bloodhound(self, start_oid: str) -> dict:
        """BloodHound-equivalent: shortest path over CANONICAL edges only — what a
        rule-based shortest-path query finds, with no property inference."""
        if not self.goal_oid or not self.canonical_filter:
            return {"reachable": False, "hops": -1}
        q = (
            f"MATCH (s {{objectid:$s}}), (g {{objectid:$g}}) "
            f"OPTIONAL MATCH p = shortestPath((s)-[:{self.canonical_filter}*1..15]->(g)) "
            f"RETURN p IS NOT NULL AS reachable, "
            f"CASE WHEN p IS NULL THEN -1 ELSE length(p) END AS hops"
        )
        rows = run_read(self.driver, q, database=self.database, s=start_oid, g=self.goal_oid)
        if not rows:
            return {"reachable": False, "hops": -1}
        return {"reachable": bool(rows[0]["reachable"]), "hops": rows[0]["hops"]}

    def bloodhound_path(self, start_oid: str) -> list[str]:
        """The BloodHound-equivalent canonical shortest path as an ordered list of
        node object ids (``[]`` if the canonical query finds none). This is what a
        rule-based tool would draw — the overlay the reader agent is measured against."""
        if not self.goal_oid or not self.canonical_filter or not start_oid:
            return []
        q = (
            f"MATCH (s {{objectid:$s}}), (g {{objectid:$g}}) "
            f"OPTIONAL MATCH p = shortestPath((s)-[:{self.canonical_filter}*1..15]->(g)) "
            f"RETURN CASE WHEN p IS NULL THEN [] ELSE [n IN nodes(p) | n.objectid] END AS oids"
        )
        rows = run_read(self.driver, q, database=self.database, s=start_oid, g=self.goal_oid)
        return list(rows[0]["oids"]) if rows and rows[0]["oids"] else []


# --------------------------------------------------------------------------
# Verify a proposed path hop-by-hop
# --------------------------------------------------------------------------
def verify_path(ctx: ScoringContext, tokens: list[str], expected_start_oid: str | None = None) -> dict:
    resolved = [ctx.resolve(t) for t in tokens]
    unresolved = [t for t, o in zip(tokens, resolved) if o is None]

    hop_edges = []
    derived_steps = 0
    connected = len(tokens) >= 2 and not unresolved
    if connected:
        for a, b in zip(resolved, resolved[1:]):
            kind = ctx.hop_kind(a, b)               # ('edge',t) | ('inferred',rule) | None
            label = kind[1] if kind else None
            inferred = bool(kind) and kind[0] == "inferred"
            hop_edges.append({"from": a, "to": b, "edge": label, "inferred": inferred})
            if kind is None:
                connected = False
            elif inferred:
                derived_steps += 1

    reaches_goal = bool(resolved) and resolved[-1] == ctx.goal_oid
    starts_ok = expected_start_oid is None or (bool(resolved) and resolved[0] == expected_start_oid)
    valid = connected and reaches_goal and len(tokens) >= 2 and not unresolved
    hallucinated = bool(unresolved) or any(h["edge"] is None for h in hop_edges)
    return {
        "valid": valid,
        "hallucinated": hallucinated,
        "hops": (len(tokens) - 1) if len(tokens) >= 2 else -1,
        "reaches_goal": reaches_goal,
        "starts_ok": starts_ok,
        "unresolved": unresolved,
        "hop_edges": hop_edges,
        "derived_steps": derived_steps,        # inferred (non-edge) hops used
        "uses_derived": derived_steps > 0,
    }


# --------------------------------------------------------------------------
# Top-level: score one AgentResult
# --------------------------------------------------------------------------
def score_agent_result(ctx: ScoringContext, result, start_oid: str) -> dict:
    """Score one agent run against the graph and the BloodHound baseline."""
    answer = getattr(result, "answer", str(result)) or ""
    path_field = getattr(result, "path_field", None)
    finished = getattr(result, "finished", True)
    base = ctx.baseline(start_oid)      # TRUE reachability (all attack edges)
    bh = ctx.bloodhound(start_oid)      # BloodHound-canonical reachability

    if not finished:
        # The agent never produced a final answer (ran out of steps or emitted
        # unparseable output). That's an incomplete run, NOT a hallucination —
        # it didn't fabricate an edge, it just didn't finish.
        return {
            "proposed_path": answer,
            "path_valid": False,
            "hallucinated_edge": False,
            "correct": False,
            "declared_no_path": False,
            "incomplete": True,
            "agent_hops": -1,
            "derived_steps": 0,
            "baseline_reachable": base["reachable"],
            "baseline_hops": base["hops"],
            "bloodhound_reachable": bh["reachable"],
            "bloodhound_hops": bh["hops"],
            "beats_bloodhound": False,
            "matches_baseline": False,
            "optimal": False,
        }

    tokens = parse_path_tokens(answer, path_field)
    declared_no_path = (not tokens) or ("NO PATH" in answer.upper())

    if declared_no_path:
        path_valid = False
        hallucinated = False
        agent_hops = -1
        derived_steps = 0
        # "correct" = agent was right to give up (no TRUE path exists either)
        correct = not base["reachable"]
    else:
        v = verify_path(ctx, tokens, expected_start_oid=start_oid)
        path_valid = v["valid"]
        hallucinated = v["hallucinated"]
        agent_hops = v["hops"]
        derived_steps = v["derived_steps"]
        correct = v["valid"] and base["reachable"]

    # The headline "vs BloodHound" result: the agent found a REAL path that uses at
    # least one INFERRED step (not in the collected graph as an edge) where the
    # canonical shortest-path query finds none. Structural — not a filter choice.
    beats_bloodhound = bool(path_valid and derived_steps > 0 and not bh["reachable"])

    return {
        "proposed_path": answer,
        "path_valid": path_valid,
        "hallucinated_edge": hallucinated,
        "correct": correct,
        "declared_no_path": declared_no_path,
        "incomplete": False,
        "agent_hops": agent_hops,
        "derived_steps": derived_steps,
        "baseline_reachable": base["reachable"],
        "baseline_hops": base["hops"],
        "bloodhound_reachable": bh["reachable"],
        "bloodhound_hops": bh["hops"],
        "beats_bloodhound": beats_bloodhound,
        "matches_baseline": path_valid == base["reachable"],
        "optimal": bool(path_valid and base["reachable"] and agent_hops == base["hops"]),
    }


# --------------------------------------------------------------------------
# Backward-compat: the original simple reachability score
# --------------------------------------------------------------------------
def path_is_valid(start_oid: str, goal_oid: str) -> bool:
    result = check_path_exists(start_oid, goal_oid)
    return bool(result and result["exists"])


def score_run(start_oid: str, goal_oid: str) -> dict:
    result = check_path_exists(start_oid, goal_oid)
    if result is None:
        return {"path_valid": False, "hallucinated_edge": True, "hops": -1, "nodes": [], "edges": []}
    return {
        "path_valid": result["exists"],
        "hallucinated_edge": not result["exists"],
        "hops": result["hops"],
        "nodes": result["nodes"],
        "edges": result["edges"],
    }
