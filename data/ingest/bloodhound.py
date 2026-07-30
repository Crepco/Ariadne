"""Ingest a real BloodHound / SharpHound export into Neo4j.

BloodHound's collector (SharpHound, or BloodHound-CE) writes a set of JSON files —
``*_users.json``, ``*_groups.json``, ``*_computers.json``, ``*_domains.json`` (often
zipped) — each shaped ``{"meta": {"type": ...}, "data": [ ...objects... ]}``. This
module normalises those objects onto the *same* graph Ariadne's synthetic
generator produces: canonical edges only (``schema.CANONICAL_EDGES``) plus the
node properties the inference rules read (``hasspn``, ``crackable``,
``roastable_target``, ``unconstraineddelegation``). So the reader agent, verifier,
checks, and chat assistant all run unchanged on real data.

``crackable`` is not collected by BloodHound (it depends on offline cracking), so
it is set by a documented heuristic (``--crackable``); ``roastable_target`` is
derived from a crackable service account's host session when one exists.

Supported edge sources (legacy SharpHound shape; BHCE is close): group ``Members``
(MemberOf), object ``Aces`` (ACL RightName -> control edge), and computer
``LocalAdmins``/``Sessions``/``RemoteDesktopUsers``/``PSRemoteUsers``/``DcomUsers``.
Unrecognised edge types are dropped (only canonical edges are written).

Usage::

    python data/ingest/bloodhound.py --from path/to/export_dir --wipe
    python data/ingest/bloodhound.py --from export.zip --crackable spn-admincount
"""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from ariadne.schema import BASE_LABEL, CANONICAL_EDGES

_CANON = set(CANONICAL_EDGES)

# BloodHound meta.type / filename token -> our node label.
_TYPE_LABEL = {"users": "User", "groups": "Group", "computers": "Computer", "domains": "Domain"}

# ACL RightName (from an Ace) -> canonical edge type.
_ACE_EDGE = {
    "GenericAll": "GenericAll",
    "GenericWrite": "GenericWrite",
    "WriteDacl": "WriteDacl",
    "WriteOwner": "WriteOwner",
    "Owns": "Owns",
    "Owner": "Owns",
    "AllExtendedRights": "AllExtendedRights",
    "ForceChangePassword": "ForceChangePassword",
    "AddMember": "AddMember",
    "AddMembers": "AddMember",
    "GetChangesAll": "DCSync",           # simplification: GetChangesAll implies DCSync
    "DCSync": "DCSync",
}

# Computer principal-list key -> canonical edge (principal -> computer).
_COMPUTER_ACCESS = {
    "LocalAdmins": "AdminTo",
    "AdminTo": "AdminTo",
    "RemoteDesktopUsers": "CanRDP",
    "PSRemoteUsers": "CanPSRemote",
    "DcomUsers": "ExecuteDCOM",
}

# Computer session-list keys (BHCE splits sessions across several collections).
_SESSION_KEYS = ("Sessions", "PrivilegedSessions", "RegistrySessions")


# ---------------------------------------------------------------------------
# Reading files
# ---------------------------------------------------------------------------
def load_export(path: str | Path) -> dict[str, list[dict]]:
    """Read a BloodHound export dir or zip -> ``{label: [objects]}``."""
    path = Path(path)
    by_label: dict[str, list[dict]] = defaultdict(list)

    def ingest_blob(name: str, blob: dict) -> None:
        kind = (blob.get("meta", {}) or {}).get("type") or _type_from_name(name)
        label = _TYPE_LABEL.get((kind or "").lower())
        if label:
            by_label[label].extend(blob.get("data", []) or [])

    if path.is_dir():
        for f in sorted(path.glob("*.json")):
            ingest_blob(f.name, json.loads(f.read_text(encoding="utf-8")))
    elif path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            for n in sorted(z.namelist()):
                if n.endswith(".json"):
                    ingest_blob(n, json.loads(z.read(n).decode("utf-8")))
    else:  # a single json file
        ingest_blob(path.name, json.loads(path.read_text(encoding="utf-8")))
    return dict(by_label)


def _type_from_name(name: str) -> str | None:
    low = name.lower()
    for token in _TYPE_LABEL:
        if token in low:
            return token
    return None


# ---------------------------------------------------------------------------
# Normalisation (pure — unit-tested without a database)
# ---------------------------------------------------------------------------
def _oid(obj: dict) -> str | None:
    props = obj.get("Properties") or {}
    return obj.get("ObjectIdentifier") or props.get("objectid") or props.get("objectsid")


def _principals(value: Any) -> Iterable[str]:
    """Yield principal object ids from a BloodHound list (or {'Results': [...]})."""
    items = value.get("Results", value) if isinstance(value, dict) else value
    for it in items or []:
        if isinstance(it, dict):
            sid = it.get("ObjectIdentifier") or it.get("MemberId") or it.get("PrincipalSID")
            if sid:
                yield sid
        elif isinstance(it, str):
            yield it


def build_graph_from_export(
    by_label: dict[str, list[dict]],
    *,
    crackable: str = "spn-admincount",
    domain: str = "",
) -> dict[str, Any]:
    """Normalise BloodHound objects into Ariadne's ``{nodes, edges, ...}`` graph."""
    nodes: list[dict] = []
    edges: set[tuple[str, str, str]] = set()
    goal_oid = None
    session_host: dict[str, str] = {}   # crackable-candidate user oid -> a host computer

    for label, objects in by_label.items():
        for obj in objects:
            oid = _oid(obj)
            if not oid:
                continue
            p = obj.get("Properties") or {}
            name = (p.get("name") or oid).upper()
            hasspn = bool(p.get("hasspn"))
            props = {
                "objectid": oid,
                "name": name,
                "domain": (p.get("domain") or domain).upper(),
                "hasspn": hasspn,
                "crackable": _is_crackable(crackable, p),
                # Inference properties: honour a pre-annotated value if the export
                # carries one (e.g. an Ariadne round-trip), else leave to derivation.
                "roastable_target": p.get("roastable_target"),
                "cred_target": p.get("cred_target"),
                "unconstraineddelegation": bool(p.get("unconstraineddelegation")),
                "esc1": bool(p.get("esc1")),
                "admincount": bool(p.get("admincount")),
                "highvalue": bool(p.get("highvalue")),
                "is_dc": bool(p.get("isdc") or p.get("is_dc")),
                "enabled": p.get("enabled", True),
            }
            nodes.append({"label": label, "objectid": oid, "props": props})
            if label == "Group" and name.startswith("DOMAIN ADMINS@"):
                goal_oid = oid

            # -- edges from this object --
            # PrimaryGroupSID: every principal is an implicit member of its primary
            # group. Real exports lean on this heavily; a synthetic graph rarely has it.
            pgs = p.get("primarygroupsid") or obj.get("PrimaryGroupSID")
            if pgs and pgs != oid:
                edges.add(("MemberOf", oid, pgs))
            if label == "Group":
                for m in _principals(obj.get("Members")):
                    edges.add(("MemberOf", m, oid))
            for ace in obj.get("Aces") or []:
                etype = _ACE_EDGE.get(ace.get("RightName"))
                src = ace.get("PrincipalSID")
                if etype in _CANON and src and src != oid:
                    edges.add((etype, src, oid))
            if label == "Computer":
                for key, etype in _COMPUTER_ACCESS.items():
                    for src in _principals(obj.get(key)):
                        edges.add((etype, src, oid))
                for skey in _SESSION_KEYS:
                    for u in _principals(obj.get(skey)):
                        edges.add(("HasSession", oid, u))   # computer -> user
                        session_host.setdefault(u, oid)

    # Derive roastable_target: a crackable service account exposed on a host it
    # has a session on (best-effort, since BloodHound doesn't collect this link).
    # A value pre-annotated on the host (Ariadne round-trip) is left untouched.
    for n in nodes:
        u = n["objectid"]
        if n["props"]["crackable"] and u in session_host:
            host = next((h for h in nodes if h["objectid"] == session_host[u]), None)
            if host and not host["props"].get("roastable_target"):
                host["props"]["roastable_target"] = u

    return {"nodes": nodes, "edges": edges, "goal": goal_oid, "domain": domain}


def _is_crackable(mode: str, props: dict) -> bool:
    """Heuristic for which SPN accounts have a crackable password.

    An explicit ``crackable`` property (e.g. an Ariadne round-trip export) wins;
    otherwise apply the heuristic, since BloodHound cannot know crack-ability.
    """
    if props.get("crackable") is not None:
        return bool(props.get("crackable"))
    if not props.get("hasspn"):
        return False
    if mode == "all-spn":
        return True
    if mode == "spn-admincount":          # privileged service accounts (default)
        return bool(props.get("admincount"))
    return False


# ---------------------------------------------------------------------------
# Neo4j write path (reuses the shared batched writer)
# ---------------------------------------------------------------------------
def write_to_neo4j(graph: dict[str, Any], *, wipe: bool, database: str | None = None) -> None:
    from ariadne.config import load_neo4j_config
    from ariadne.db import ensure_indexes, get_driver, node_upsert_query, run_write_batches

    if database is None:
        database = load_neo4j_config().database
    driver = get_driver()
    ensure_indexes(driver, database)
    if wipe:
        with driver.session(database=database) as session:
            session.run("MATCH (n) DETACH DELETE n").consume()

    by_label: dict[str, list[dict]] = defaultdict(list)
    for n in graph["nodes"]:
        by_label[n["label"]].append({"objectid": n["objectid"], "props": n["props"]})
    for label, rows in by_label.items():
        run_write_batches(driver, node_upsert_query(label), rows, database=database)

    by_type: dict[str, list[dict]] = defaultdict(list)
    for etype, src, dst in graph["edges"]:
        if etype not in _CANON:          # guard against Cypher injection
            raise ValueError(f"Non-canonical edge type: {etype!r}")
        by_type[etype].append({"src": src, "dst": dst})
    for etype, rows in by_type.items():
        run_write_batches(
            driver,
            f"UNWIND $rows AS row "
            f"MATCH (a:{BASE_LABEL} {{objectid: row.src}}) "
            f"MATCH (b:{BASE_LABEL} {{objectid: row.dst}}) "
            f"MERGE (a)-[:{etype}]->(b)",
            rows,
            database=database,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="source", required=True, help="export directory, .zip, or .json file")
    ap.add_argument("--crackable", choices=["spn-admincount", "all-spn", "none"], default="spn-admincount",
                    help="heuristic for which SPN accounts are crackable (default: privileged ones)")
    ap.add_argument("--domain", default="", help="fallback domain if objects omit one")
    ap.add_argument("--wipe", action="store_true", help="delete existing nodes first")
    ap.add_argument("--dry-run", action="store_true", help="parse + report only, no database write")
    args = ap.parse_args()

    by_label = load_export(args.source)
    graph = build_graph_from_export(by_label, crackable=args.crackable, domain=args.domain)
    counts = {lbl: len(objs) for lbl, objs in by_label.items()}
    edge_counts: dict[str, int] = defaultdict(int)
    for etype, _, _ in graph["edges"]:
        edge_counts[etype] += 1
    print(f"Parsed {sum(counts.values())} objects {counts}; {len(graph['edges'])} canonical edges")
    print("  edges by type: " + ", ".join(f"{k}={v}" for k, v in sorted(edge_counts.items())))
    print(f"  goal (Domain Admins) objectid: {graph['goal']}")
    if args.dry_run:
        print("Dry run: nothing written.")
        return
    print("Writing to Neo4j ...")
    write_to_neo4j(graph, wipe=args.wipe)
    print("Done. Run verify.py or the reader agent against the ingested graph.")


if __name__ == "__main__":
    main()
