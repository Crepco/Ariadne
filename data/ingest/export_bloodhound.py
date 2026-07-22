"""Export an Ariadne graph as a BloodHound-CE-shaped JSON collection.

This is the inverse of ``bloodhound.py``: it takes the ``{nodes, edges, ...}``
graph the synthetic generator (or any Ariadne pipeline) produces and writes the
``*_users.json`` / ``*_groups.json`` / ``*_computers.json`` / ``*_domains.json``
files a real SharpHound / BloodHound-CE collection looks like — each shaped
``{"meta": {"type": ...}, "data": [ ...objects... ]}``.

Two uses:

* **Round-trip proof.** ``bloodhound.build_graph_from_export`` should reconstruct
  the *same* canonical edges and inference properties from these files, so the
  whole reader pipeline (checks / agent / verifier / chat) can be exercised on a
  BloodHound-shaped export without touching a real, sensitive collection.
* **A safe, shareable sample export.** ``--out <dir>`` writes a realistic-looking
  BloodHound collection built from synthetic data — useful as a demo fixture or a
  fully offline "real data" walkthrough (see ``data/ingest/README.md``).

Edges are inverted back into the collection buckets the ingest reads:
``MemberOf`` -> the group's ``Members``; ACL control edges -> the target's
``Aces`` (``{PrincipalSID, RightName}``); ``AdminTo``/``CanRDP``/``CanPSRemote``/
``ExecuteDCOM`` -> the computer's ``LocalAdmins``/``RemoteDesktopUsers``/
``PSRemoteUsers``/``DcomUsers``; ``HasSession`` -> the computer's ``Sessions``;
``DCSync`` -> a ``DCSync`` ACE on the domain. Inference properties
(``roastable_target``, ``cred_target``, ``unconstraineddelegation``, ``esc1``,
``hasspn``, ``crackable``) ride along as node ``Properties`` so the round trip is
loss-free.

Usage::

    python data/ingest/export_bloodhound.py --out /tmp/ariadne_export --seed 7
    # then re-ingest it exactly like a real collection:
    python data/ingest/bloodhound.py --from /tmp/ariadne_export --wipe
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

# Our node label -> BloodHound meta.type / filename token.
_LABEL_TYPE = {"User": "users", "Group": "groups", "Computer": "computers", "Domain": "domains"}

# Canonical edge -> the computer principal-list it inverts to (principal -> computer).
_ACCESS_LIST = {
    "AdminTo": "LocalAdmins",
    "CanRDP": "RemoteDesktopUsers",
    "CanPSRemote": "PSRemoteUsers",
    "ExecuteDCOM": "DcomUsers",
}

# Canonical ACL edge -> the RightName it becomes in the target object's Aces.
_ACL_RIGHTS = {
    "GenericAll": "GenericAll",
    "GenericWrite": "GenericWrite",
    "WriteDacl": "WriteDacl",
    "WriteOwner": "WriteOwner",
    "Owns": "Owns",
    "AllExtendedRights": "AllExtendedRights",
    "ForceChangePassword": "ForceChangePassword",
    "AddMember": "AddMember",
    "DCSync": "DCSync",
}


def graph_to_objects(graph: dict[str, Any]) -> dict[str, list[dict]]:
    """Invert an Ariadne graph into ``{label: [BloodHound objects]}``.

    The output matches ``bloodhound.load_export``'s shape exactly, so
    ``bloodhound.build_graph_from_export(graph_to_objects(g))`` is a round trip.
    """
    members: dict[str, list[dict]] = defaultdict(list)     # group oid -> members
    sessions: dict[str, list[dict]] = defaultdict(list)    # computer oid -> sessions
    access: dict[str, dict[str, list[dict]]] = {           # list-key -> computer oid -> principals
        key: defaultdict(list) for key in _ACCESS_LIST.values()
    }
    aces: dict[str, list[dict]] = defaultdict(list)        # target oid -> Aces

    for etype, src, dst in graph["edges"]:
        if etype == "MemberOf":
            members[dst].append({"ObjectIdentifier": src})
        elif etype == "HasSession":
            sessions[src].append({"ObjectIdentifier": dst})
        elif etype in _ACCESS_LIST:
            access[_ACCESS_LIST[etype]][dst].append({"ObjectIdentifier": src})
        elif etype in _ACL_RIGHTS:
            aces[dst].append({"PrincipalSID": src, "RightName": _ACL_RIGHTS[etype]})
        else:  # defensive: the graph should only carry canonical edges
            raise ValueError(f"Cannot export non-canonical edge type: {etype!r}")

    by_label: dict[str, list[dict]] = defaultdict(list)
    for n in graph["nodes"]:
        oid = n["objectid"]
        label = n["label"]
        # Node properties ride along verbatim (minus null-valued keys, as a real
        # collector would omit them); inference props are just more properties.
        props = {k: v for k, v in n["props"].items() if v is not None}
        props.setdefault("objectid", oid)
        obj: dict[str, Any] = {"ObjectIdentifier": oid, "Properties": props}
        if aces.get(oid):
            obj["Aces"] = aces[oid]
        if label == "Group":
            obj["Members"] = members.get(oid, [])
        elif label == "Computer":
            for key in _ACCESS_LIST.values():
                obj[key] = access[key].get(oid, [])
            obj["Sessions"] = sessions.get(oid, [])
        by_label[label].append(obj)

    return dict(by_label)


def write_export(graph: dict[str, Any], out_dir: str | Path) -> list[Path]:
    """Write the inverted graph as BloodHound-CE JSON files into ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    domain = (graph.get("domain") or "ariadne").lower()
    by_label = graph_to_objects(graph)
    written: list[Path] = []
    for label, objects in by_label.items():
        kind = _LABEL_TYPE[label]
        blob = {"meta": {"type": kind, "count": len(objects), "version": 5}, "data": objects}
        path = out / f"{domain}_{kind}.json"
        path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# CLI — build a synthetic graph and export it as a shareable BloodHound sample.
# ---------------------------------------------------------------------------
def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generator"))
    import generate  # noqa: E402  (path set above)

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="output directory for the *_users.json etc. files")
    ap.add_argument("--users", type=int, default=120)
    ap.add_argument("--computers", type=int, default=25)
    ap.add_argument("--groups", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--domain", default="ARIADNE.LOCAL")
    ap.add_argument("--no-plant", dest="plant", action="store_false", help="skip planted chains")
    args = ap.parse_args()

    graph = generate.build_graph(
        n_users=args.users, n_computers=args.computers, n_groups=args.groups,
        seed=args.seed, domain=args.domain, plant=args.plant,
    )
    paths = write_export(graph, args.out)
    counts = defaultdict(int)
    for n in graph["nodes"]:
        counts[n["label"]] += 1
    print(f"Exported {len(graph['nodes'])} objects {dict(counts)}, {len(graph['edges'])} edges")
    for p in paths:
        print(f"  wrote {p}")
    print(f"Re-ingest with:  python data/ingest/bloodhound.py --from {args.out} --wipe")


if __name__ == "__main__":
    main()
