"""Scoring for one agent run.

Two things are measured:

1. **Is the agent's proposed path real?** We parse the ordered nodes the agent
   claims and verify *each consecutive hop* against the graph. A claimed hop with
   no matching edge (or an unresolvable node) is a hallucination. This is the part
   the old ``score_run`` never did — it only checked start→goal reachability.

2. **How does it compare to BloodHound?** The ground-truth shortest path over the
   same traversable edge set is our BloodHound-equivalent baseline. We record
   whether the baseline is reachable, its hop count, and whether the agent matched
   or found the optimal-length path.

``score_run`` (simple reachability) is kept for backward compatibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ariadne.config import load_neo4j_config
from ariadne.db import get_driver, run_read
from ariadne.schema import CANONICAL_EDGES, GOAL_GROUP, TRAVERSABLE_EDGES
from ariadne.tools import check_path_exists

_ARROW = re.compile(r"->|=>|→")
_EDGE_SET = {e.upper() for e in TRAVERSABLE_EDGES}


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
    oids: set = field(default_factory=set)
    rel_filter: str = ""            # ALL traversable edges (agent / true reach)
    canonical_filter: str = ""      # canonical edges only (BloodHound baseline)

    @classmethod
    def load(cls) -> "ScoringContext":
        database = load_neo4j_config().database
        driver = get_driver()

        name_to_oid: dict[str, str] = {}
        oids: set[str] = set()
        for row in run_read(
            driver, "MATCH (n) RETURN n.objectid AS oid, n.name AS name", database=database
        ):
            oid, name = row["oid"], row["name"]
            if not oid:
                continue
            oids.add(oid)
            if name:
                name_to_oid[name.upper()] = oid
                name_to_oid[name.split("@")[0].upper()] = oid  # short name too

        goal_rows = run_read(
            driver,
            "MATCH (g:Group) WHERE g.name STARTS WITH $p RETURN g.objectid AS oid",
            database=database,
            p=f"{GOAL_GROUP}@",
        )
        goal_oid = goal_rows[0]["oid"] if goal_rows else None

        present = {
            r["t"]
            for r in run_read(
                driver,
                "CALL db.relationshipTypes() YIELD relationshipType AS t RETURN t",
                database=database,
            )
        }
        rel_filter = "|".join(e for e in TRAVERSABLE_EDGES if e in present)
        canonical_filter = "|".join(e for e in CANONICAL_EDGES if e in present)
        return cls(driver, database, goal_oid, name_to_oid, oids, rel_filter, canonical_filter)

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

    def edge_between(self, a_oid: str, b_oid: str):
        """Return the type of a direct traversable edge a->b, or None."""
        rows = run_read(
            self.driver,
            "MATCH (a {objectid:$a})-[r]->(b {objectid:$b}) "
            "WHERE type(r) IN $edges RETURN type(r) AS e LIMIT 1",
            database=self.database,
            a=a_oid,
            b=b_oid,
            edges=list(TRAVERSABLE_EDGES),
        )
        return rows[0]["e"] if rows else None

    def _shortest(self, start_oid: str, rel_filter: str) -> dict:
        """Shortest path start -> Domain Admins over the given edge-type filter."""
        if not self.goal_oid or not rel_filter:
            return {"reachable": False, "hops": -1}
        q = (
            f"MATCH (s {{objectid:$s}}), (g {{objectid:$g}}) "
            f"OPTIONAL MATCH p = shortestPath((s)-[:{rel_filter}*1..15]->(g)) "
            f"RETURN p IS NOT NULL AS reachable, "
            f"CASE WHEN p IS NULL THEN -1 ELSE length(p) END AS hops"
        )
        rows = run_read(self.driver, q, database=self.database, s=start_oid, g=self.goal_oid)
        if not rows:
            return {"reachable": False, "hops": -1}
        return {"reachable": bool(rows[0]["reachable"]), "hops": rows[0]["hops"]}

    def baseline(self, start_oid: str) -> dict:
        """TRUE ground truth: shortest path over ALL attack edges (canonical +
        advanced). This is what the agent is *actually* scored against."""
        return self._shortest(start_oid, self.rel_filter)

    def bloodhound(self, start_oid: str) -> dict:
        """BloodHound-equivalent: shortest path over CANONICAL edges only — what a
        rule-based shortest-path query would find, ignoring advanced tradecraft."""
        return self._shortest(start_oid, self.canonical_filter)


# --------------------------------------------------------------------------
# Verify a proposed path hop-by-hop
# --------------------------------------------------------------------------
def verify_path(ctx: ScoringContext, tokens: list[str], expected_start_oid: str | None = None) -> dict:
    resolved = [ctx.resolve(t) for t in tokens]
    unresolved = [t for t, o in zip(tokens, resolved) if o is None]

    hop_edges = []
    connected = len(tokens) >= 2 and not unresolved
    if connected:
        for a, b in zip(resolved, resolved[1:]):
            edge = ctx.edge_between(a, b)
            hop_edges.append({"from": a, "to": b, "edge": edge})
            if edge is None:
                connected = False

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
        # "correct" = agent was right to give up (no TRUE path exists either)
        correct = not base["reachable"]
    else:
        v = verify_path(ctx, tokens, expected_start_oid=start_oid)
        path_valid = v["valid"]
        hallucinated = v["hallucinated"]
        agent_hops = v["hops"]
        correct = v["valid"] and base["reachable"]

    # The headline "vs BloodHound" result: the agent found a REAL path where the
    # rule-based canonical shortest-path query finds none (i.e. the route needs
    # advanced tradecraft). Only counts when the agent's path is genuinely valid.
    beats_bloodhound = bool(path_valid and not bh["reachable"])

    return {
        "proposed_path": answer,
        "path_valid": path_valid,
        "hallucinated_edge": hallucinated,
        "correct": correct,
        "declared_no_path": declared_no_path,
        "incomplete": False,
        "agent_hops": agent_hops,
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
