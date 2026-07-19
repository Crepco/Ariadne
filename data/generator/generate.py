"""Synthetic Active Directory graph generator (BloodHound schema).

Builds a randomized-but-realistic AD forest — users, groups, computers, and the
attack-relevant relationship edges between them — and writes it into Neo4j.

We roll our own generator instead of DBCreator because:
  * DBCreator targets older Neo4j and frequently breaks on Neo4j 5.x / Aura;
  * a seeded generator is fully reproducible (same seed -> same graph);
  * we control the exact schema and edge density.

Relationships are random, so we do NOT hand-pick "the answer is path X". The
ground-truth attack path is computed *after* generation with the same Cypher
shortest-path query BloodHound uses (see verify.py) — that is the answer key.

Usage (from the repo root, with the venv active)::

    # Offline: build in memory and report solvability, no database needed
    python data/generator/generate.py --dry-run

    # Write a ~400-node graph to Neo4j (wipes existing data first)
    python data/generator/generate.py --wipe

    # A larger graph for the scaling curve
    python data/generator/generate.py --users 1500 --computers 300 --groups 150 --wipe
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from ariadne.config import DEFAULT_DOMAIN
from ariadne.inference import true_reachable
from ariadne.schema import (
    CANONICAL_EDGES,
    CONTROL_EDGES_ANY,
    CONTROL_EDGES_GROUP,
    CONTROL_EDGES_USER,
    EXECUTION_EDGES,
    HIGH_VALUE_GROUPS,
    INFERENCE_PROPERTIES,
    TRAVERSABLE_EDGES,
    WELL_KNOWN_GROUPS,
)

# Remote-access edges (everything in EXECUTION_EDGES except AdminTo) used for
# lateral movement toward exposed sessions.
LATERAL_EDGES = [e for e in EXECUTION_EDGES if e != "AdminTo"]

# RID offset for planted-chain nodes, kept well clear of generated RIDs so the
# two never collide.
PLANT_RID_BASE = 900_000


# ---------------------------------------------------------------------------
# In-memory graph construction (no database required)
# ---------------------------------------------------------------------------
def _node(label: str, objectid: str, props: dict[str, Any]) -> dict[str, Any]:
    return {"label": label, "objectid": objectid, "props": {"objectid": objectid, **props}}


def _edge(etype: str, src: str, dst: str) -> tuple[str, str, str]:
    return (etype, src, dst)


def build_graph(
    *,
    n_users: int = 300,
    n_computers: int = 60,
    n_groups: int = 40,
    density: float = 0.6,
    seed: int = 1337,
    domain: str = DEFAULT_DOMAIN,
    plant: bool = True,
) -> dict[str, Any]:
    """Construct the graph in memory. Returns nodes, edges, and metadata."""
    rng = random.Random(seed)
    domain = domain.upper()

    domain_sid = "S-1-5-21-" + "-".join(
        str(rng.randint(1_000_000_000, 4_000_000_000)) for _ in range(3)
    )

    def sid(rid: int) -> str:
        return f"{domain_sid}-{rid}"

    nodes: list[dict[str, Any]] = []
    edges: set[tuple[str, str, str]] = set()

    # --- Domain node ---
    domain_oid = domain_sid
    nodes.append(_node("Domain", domain_oid, {"name": domain, "domain": domain}))

    # --- Well-known groups (incl. the high-value targets) ---
    special: dict[str, str] = {}
    for rid, gname in WELL_KNOWN_GROUPS.items():
        oid = sid(rid)
        high_value = gname in HIGH_VALUE_GROUPS
        nodes.append(
            _node(
                "Group",
                oid,
                {
                    "name": f"{gname}@{domain}",
                    "domain": domain,
                    "highvalue": high_value,
                    "admincount": high_value,
                },
            )
        )
        special[gname] = oid
    goal = special["DOMAIN ADMINS"]

    # --- Regular groups ---
    rid = 1104
    group_oids: list[str] = []
    for i in range(n_groups):
        oid = sid(rid)
        rid += 1
        nodes.append(
            _node(
                "Group",
                oid,
                {
                    "name": f"GROUP{i:04d}@{domain}",
                    "domain": domain,
                    "highvalue": False,
                    "admincount": False,
                },
            )
        )
        group_oids.append(oid)

    # --- Users ---
    user_oids: list[str] = []
    crackable_users: list[str] = []      # SPN accounts with a weak (crackable) password
    for i in range(n_users):
        oid = sid(rid)
        rid += 1
        hasspn = rng.random() < 0.08
        # Only a subset of SPN accounts have a crackable (weak) password — those
        # are the real kerberoast pivots. This is a PROPERTY, not an edge; the
        # roast step is inferred from it (see ariadne.inference).
        crackable = hasspn and rng.random() < 0.35
        nodes.append(
            _node(
                "User",
                oid,
                {
                    "name": f"USER{i:04d}@{domain}",
                    "domain": domain,
                    "enabled": True,
                    "hasspn": hasspn,
                    "crackable": crackable,
                    "admincount": False,
                    "owned": False,
                },
            )
        )
        user_oids.append(oid)
        if crackable:
            crackable_users.append(oid)

    # --- Computers ---
    comp_oids: list[str] = []
    comp_nodes: list[dict] = []          # node dicts, so we can tag roastable_target later
    n_dcs = max(1, n_computers // 40)
    for i in range(n_computers):
        oid = sid(rid)
        rid += 1
        # Unconstrained delegation is a PROPERTY; the coerce-and-impersonate step
        # to domain dominance is inferred from it, not stored as an edge.
        unconstrained = i >= n_dcs and rng.random() < 0.05   # non-DC hosts only
        cnode = _node(
            "Computer",
            oid,
            {
                "name": f"COMP{i:04d}.{domain}",
                "domain": domain,
                "enabled": True,
                "is_dc": i < n_dcs,
                "unconstraineddelegation": unconstrained,
            },
        )
        nodes.append(cnode)
        comp_oids.append(oid)
        comp_nodes.append(cnode)

    all_groups = group_oids + list(special.values())
    principals = user_oids + all_groups

    # --- Base membership: every user is in DOMAIN USERS ---
    for u in user_oids:
        edges.add(_edge("MemberOf", u, special["DOMAIN USERS"]))

    # --- A handful of legitimate Domain Admins (so the goal is non-empty) ---
    n_da = max(1, n_users // 150)
    for u in rng.sample(user_oids, n_da):
        edges.add(_edge("MemberOf", u, goal))

    # --- Random user -> group memberships ---
    for u in user_oids:
        k = rng.randint(1, min(3, len(group_oids))) if group_oids else 0
        for g in rng.sample(group_oids, k):
            edges.add(_edge("MemberOf", u, g))

    # --- Group nesting (a classic source of non-obvious paths) ---
    for i, g in enumerate(group_oids):
        if rng.random() < 0.30:
            candidates = group_oids[i + 1 :] + [special["ADMINISTRATORS"], goal]
            edges.add(_edge("MemberOf", g, rng.choice(candidates)))

    # --- Local admin rights: principals AdminTo computers ---
    for c in comp_oids:
        for p in rng.sample(principals, rng.randint(0, 2)):
            edges.add(_edge("AdminTo", p, c))

    # --- Remote-access rights: lateral movement toward exposed sessions ---
    for c in comp_oids:
        for p in rng.sample(principals, rng.randint(0, 2)):
            edges.add(_edge(rng.choice(LATERAL_EDGES), p, c))

    # --- Sessions: computers expose credentials of logged-on users ---
    for c in comp_oids:
        if rng.random() < 0.6:
            for u in rng.sample(user_oids, min(rng.randint(1, 3), len(user_oids))):
                edges.add(_edge("HasSession", c, u))

    # --- ACL misconfigurations: the raw attack surface ---
    n_acl = int(density * (n_users + n_groups))
    for _ in range(n_acl):
        src = rng.choice(principals)
        roll = rng.random()
        if roll < 0.5:
            tgt = rng.choice(user_oids)
            menu = CONTROL_EDGES_ANY + CONTROL_EDGES_USER
        elif roll < 0.85:
            tgt = rng.choice(all_groups)
            menu = CONTROL_EDGES_ANY + CONTROL_EDGES_GROUP
        else:
            tgt = rng.choice(comp_oids)
            menu = CONTROL_EDGES_ANY
        if src != tgt:
            edges.add(_edge(rng.choice(menu), src, tgt))

    # --- A few DCSync rights (domain dominance) ---
    for p in rng.sample(principals, max(1, len(principals) // 250)):
        edges.add(_edge("DCSync", p, domain_oid))

    # Each crackable SPN account is exposed by one host computer (roastable_target
    # PROPERTY, not an edge): reaching that host lets you roast the account. This
    # keeps kerberoast a LOCAL inferred step, not a free jump from anywhere.
    if comp_nodes:
        for i, u in enumerate(crackable_users):
            comp_nodes[i % len(comp_nodes)]["props"]["roastable_target"] = u

    # NOTE: advanced tradecraft (kerberoast, unconstrained-delegation abuse) is
    # NOT emitted as edges. It is derived at scoring/inference time from the
    # `roastable_target` and `unconstraineddelegation` node properties, so a
    # canonical edge-traversal query structurally cannot see it.

    graph: dict[str, Any] = {
        "nodes": nodes,
        "edges": edges,
        "goal": goal,
        "domain": domain,
        "domain_oid": domain_oid,
        "specials": special,
        "user_oids": user_oids,
        "seed": seed,
        "planted": [],
    }

    if plant:
        _plant_known_chains(graph, sid)

    return graph


def _plant_known_chains(graph: dict[str, Any], sid) -> None:
    """Insert deterministic attack chains whose answers we already know.

    Gives us a hybrid dataset: realistic random bulk + a few hand-verified
    chains. Each planted chain is recorded in ``graph['planted']`` as an
    (start, expected node/edge sequence) answer key.
    """
    domain = graph["domain"]
    goal = graph["goal"]
    nodes: list[dict] = graph["nodes"]
    edges: set = graph["edges"]

    def add_user(tag: str, rid: int, hasspn: bool = False, crackable: bool = False) -> str:
        oid = sid(rid)
        nodes.append(
            _node(
                "User",
                oid,
                {
                    "name": f"PLANT_{tag}@{domain}",
                    "domain": domain,
                    "enabled": True,
                    "hasspn": hasspn,
                    "crackable": crackable,
                    "admincount": False,
                    "owned": False,
                    "planted": True,
                },
            )
        )
        return oid

    def add_group(tag: str, rid: int) -> str:
        oid = sid(rid)
        nodes.append(
            _node(
                "Group",
                oid,
                {
                    "name": f"PLANT_{tag}@{domain}",
                    "domain": domain,
                    "highvalue": False,
                    "admincount": False,
                    "planted": True,
                },
            )
        )
        return oid

    def add_computer(
        tag: str, rid: int, roastable_target: str | None = None, unconstrained: bool = False
    ) -> str:
        oid = sid(rid)
        nodes.append(
            _node(
                "Computer",
                oid,
                {
                    "name": f"PLANT_{tag}.{domain}",
                    "domain": domain,
                    "enabled": True,
                    "is_dc": False,
                    "unconstraineddelegation": unconstrained,
                    "roastable_target": roastable_target,
                    "planted": True,
                },
            )
        )
        return oid

    # Chain 1: ForceChangePassword -> MemberOf -> GenericAll(DA)
    a = add_user("A_START", PLANT_RID_BASE + 1)
    b = add_user("A_VICTIM", PLANT_RID_BASE + 2)
    g = add_group("A_MIDGROUP", PLANT_RID_BASE + 3)
    edges.add(_edge("ForceChangePassword", a, b))
    edges.add(_edge("MemberOf", b, g))
    edges.add(_edge("GenericAll", g, goal))
    graph["planted"].append(
        {
            "name": "forcechange_nested_genericall",
            "start": a,
            "nodes": [a, b, g, goal],
            "edges": ["ForceChangePassword", "MemberOf", "GenericAll"],
            "hops": 3,
            "advanced": False,
        }
    )

    # Chain 2: GenericWrite(user) -> AddMember(mid) -> MemberOf(DA)
    c = add_user("B_START", PLANT_RID_BASE + 11)
    d = add_user("B_VICTIM", PLANT_RID_BASE + 12)
    g2 = add_group("B_MIDGROUP", PLANT_RID_BASE + 13)
    edges.add(_edge("GenericWrite", c, d))
    edges.add(_edge("AddMember", d, g2))
    edges.add(_edge("MemberOf", g2, goal))
    graph["planted"].append(
        {
            "name": "genericwrite_addmember_nested",
            "start": c,
            "nodes": [c, d, g2, goal],
            "edges": ["GenericWrite", "AddMember", "MemberOf"],
            "hops": 3,
            "advanced": False,
        }
    )

    # Chain C (advanced, INFERRED): AdminTo -> [kerberoast] -> MemberOf -> GenericAll.
    # C_START admins C_HOST (canonical). C_HOST exposes the crackable service
    # account C_SVC via a roastable_target PROPERTY — reaching the host lets you
    # roast C_SVC, an INFERRED step, not an edge. BloodHound's canonical query
    # reaches only C_HOST (a dead end), so it finds no route to DA, while an agent
    # that reads the host's property escalates in 4 hops. The planted, known-answer
    # "beats BloodHound" case; only the roast hop is non-canonical.
    e = add_user("C_START", PLANT_RID_BASE + 21)
    f = add_user("C_SVC", PLANT_RID_BASE + 22, hasspn=True, crackable=True)
    host = add_computer("C_HOST", PLANT_RID_BASE + 24, roastable_target=f)
    g3 = add_group("C_MIDGROUP", PLANT_RID_BASE + 23)
    edges.add(_edge("AdminTo", e, host))
    edges.add(_edge("MemberOf", f, g3))
    edges.add(_edge("GenericAll", g3, goal))
    graph["planted"].append(
        {
            "name": "kerberoast_via_host_nested",
            "start": e,
            "nodes": [e, host, f, g3, goal],
            "edges": ["AdminTo", "Kerberoast(inferred)", "MemberOf", "GenericAll"],
            "hops": 4,
            "advanced": True,
        }
    )

    # Chain D (advanced, INFERRED): AdminTo -> [unconstrained delegation].
    # D_START admins D_HOST (canonical), which is trusted for unconstrained
    # delegation. Reaching it lets you coerce a DC and reach domain dominance — an
    # INFERRED step from the `unconstraineddelegation` property, not an edge. The
    # canonical query sees only the dead-end AdminTo, so it's BloodHound-blind.
    h = add_user("D_START", PLANT_RID_BASE + 31)
    dhost = add_computer("D_HOST", PLANT_RID_BASE + 32, unconstrained=True)
    edges.add(_edge("AdminTo", h, dhost))
    graph["planted"].append(
        {
            "name": "unconstrained_delegation_via_host",
            "start": h,
            "nodes": [h, dhost, goal],
            "edges": ["AdminTo", "UnconstrainedDelegation(inferred)"],
            "hops": 2,
            "advanced": True,
        }
    )


# ---------------------------------------------------------------------------
# Offline solvability check (pure Python BFS, no database)
# ---------------------------------------------------------------------------
def _adjacency(graph: dict[str, Any], edge_types=None) -> dict[str, list[str]]:
    allowed = set(TRAVERSABLE_EDGES if edge_types is None else edge_types)
    adj: dict[str, list[str]] = defaultdict(list)
    for etype, src, dst in graph["edges"]:
        if etype in allowed:
            adj[src].append(dst)
    return adj


def _reachable(adj: dict[str, list[str]], start: str, goal: str) -> bool:
    if start == goal:
        return True
    seen = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in adj.get(node, ()):
            if nxt == goal:
                return True
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


def _props_map(graph: dict[str, Any]) -> dict[str, dict]:
    """objectid -> the inference-relevant properties, for the rule oracle."""
    return {
        n["objectid"]: {k: n["props"].get(k) for k in INFERENCE_PROPERTIES}
        for n in graph["nodes"]
    }


def solvability_report(graph: dict[str, Any], sample: int = 100) -> dict[str, Any]:
    """Estimate what fraction of users can reach Domain Admins.

    Reports TRUE reachability (canonical edges + property-inferred steps, via
    ``ariadne.inference``) and BloodHound-canonical reachability (canonical edges
    only), so the "advanced-only" gap — users the rule-based baseline can't reach
    but a reasoning agent can via inference — is visible up front.
    """
    canon = _adjacency(graph, CANONICAL_EDGES)               # BloodHound baseline
    props = _props_map(graph)
    goal = graph["goal"]

    def truly(u: str) -> bool:
        return true_reachable(canon, props, u, goal)[0]

    users = graph["user_oids"]
    rng = random.Random(graph["seed"])
    picks = users if len(users) <= sample else rng.sample(users, sample)
    solvable = sum(truly(u) for u in picks)
    canon_solvable = sum(_reachable(canon, u, goal) for u in picks)
    advanced_only = sum(truly(u) and not _reachable(canon, u, goal) for u in picks)
    # Planted starts must always be truly solvable — sanity check the planting.
    planted_ok = all(truly(p["start"]) for p in graph["planted"])
    # Advanced planted chains must be BloodHound-blind (canonical-unreachable),
    # otherwise the "beats BloodHound" case isn't actually testable.
    adv_blind = all(
        not _reachable(canon, p["start"], goal)
        for p in graph["planted"]
        if p.get("advanced")
    )
    return {
        "sampled_users": len(picks),
        "solvable_users": solvable,
        "solvable_fraction": round(solvable / len(picks), 3) if picks else 0.0,
        "canonical_solvable_users": canon_solvable,
        "advanced_only_users": advanced_only,
        "planted_chains_reachable": planted_ok,
        "advanced_chains_bloodhound_blind": adv_blind,
    }


# ---------------------------------------------------------------------------
# Neo4j write path
# ---------------------------------------------------------------------------
def write_to_neo4j(graph: dict[str, Any], *, wipe: bool, database: str | None = None) -> None:
    from ariadne.config import load_neo4j_config
    from ariadne.db import get_driver, run_write_batches
    from ariadne.schema import NODE_LABELS

    if database is None:
        database = load_neo4j_config().database
    allowed_edges = set(TRAVERSABLE_EDGES)
    driver = get_driver()  # shared process-wide driver; closed at interpreter exit
    with driver.session(database=database) as session:
        # Uniqueness constraint per label doubles as an objectid index.
        for label in NODE_LABELS:
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_objectid IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.objectid IS UNIQUE"
            ).consume()
        if wipe:
            session.run("MATCH (n) DETACH DELETE n").consume()

    # Nodes, grouped by label (labels can't be parametrized in Cypher).
    by_label: dict[str, list[dict]] = defaultdict(list)
    for n in graph["nodes"]:
        by_label[n["label"]].append({"objectid": n["objectid"], "props": n["props"]})
    for label, rows in by_label.items():
        run_write_batches(
            driver,
            f"UNWIND $rows AS row MERGE (n:{label} {{objectid: row.objectid}}) "
            f"SET n += row.props",
            rows,
            database=database,
        )

    # Edges, grouped by type (types can't be parametrized either).
    by_type: dict[str, list[dict]] = defaultdict(list)
    for etype, src, dst in graph["edges"]:
        if etype not in allowed_edges:  # guard against Cypher injection
            raise ValueError(f"Unknown edge type: {etype!r}")
        by_type[etype].append({"src": src, "dst": dst})
    for etype, rows in by_type.items():
        run_write_batches(
            driver,
            f"UNWIND $rows AS row "
            f"MATCH (a {{objectid: row.src}}) MATCH (b {{objectid: row.dst}}) "
            f"MERGE (a)-[:{etype}]->(b)",
            rows,
            database=database,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--users", type=int, default=300)
    p.add_argument("--computers", type=int, default=60)
    p.add_argument("--groups", type=int, default=40)
    p.add_argument("--density", type=float, default=0.6, help="ACL-misconfig density")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--domain", default=DEFAULT_DOMAIN)
    p.add_argument("--no-plant", dest="plant", action="store_false", help="skip planted chains")
    p.add_argument("--wipe", action="store_true", help="delete all existing nodes first")
    p.add_argument("--dry-run", action="store_true", help="build in memory only, no database")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    graph = build_graph(
        n_users=args.users,
        n_computers=args.computers,
        n_groups=args.groups,
        density=args.density,
        seed=args.seed,
        domain=args.domain,
        plant=args.plant,
    )

    n_nodes = len(graph["nodes"])
    n_edges = len(graph["edges"])
    edge_counts: dict[str, int] = defaultdict(int)
    for etype, _, _ in graph["edges"]:
        edge_counts[etype] += 1

    print(f"Built graph: {n_nodes} nodes, {n_edges} edges  (seed={graph['seed']}, domain={graph['domain']})")
    print("  edges by type: " + ", ".join(f"{k}={v}" for k, v in sorted(edge_counts.items())))
    if graph["planted"]:
        print(f"  planted chains: {[p['name'] for p in graph['planted']]}")

    report = solvability_report(graph)
    print(
        f"  solvability: {report['solvable_users']}/{report['sampled_users']} sampled users "
        f"reach Domain Admins ({report['solvable_fraction']:.0%}); "
        f"BloodHound-canonical reaches {report['canonical_solvable_users']}, "
        f"{report['advanced_only_users']} advanced-only"
    )
    print(
        f"  planted reachable={report['planted_chains_reachable']}, "
        f"advanced chains BloodHound-blind={report['advanced_chains_bloodhound_blind']}"
    )

    # Save the planted-chain answer key next to the graph artifacts.
    if graph["planted"]:
        out = Path(__file__).resolve().parents[2] / "data" / "graphs" / "planted_answer_key.json"
        out.write_text(json.dumps(graph["planted"], indent=2), encoding="utf-8")
        print(f"  wrote answer key -> {out}")

    if args.dry_run:
        print("Dry run: nothing written to the database.")
        return

    print("Writing to Neo4j ...")
    write_to_neo4j(graph, wipe=args.wipe)
    print("Done. Run verify.py to confirm and to compute ground-truth paths.")


if __name__ == "__main__":
    main()
