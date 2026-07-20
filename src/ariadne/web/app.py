"""Flask backend for the Ariadne visualiser.

Thin JSON API over the existing pieces — Neo4j (``ariadne.db``), the ReAct agent
(``ariadne.agent.loop.run_agent``), the verifier (``ariadne.evaluation.score``),
and the vulnerability checks (``ariadne.checks``). The heavy lifting lives in
those modules; this file only turns a run into something the frontend can draw:
the explored subgraph, the verified path (the "thread"), and the verdict.

Run it::

    python -m ariadne.web.app        # or the `ariadne-web` console script
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from ariadne.agent.loop import run_agent
from ariadne.checks import CHECKS, run_check
from ariadne.db import run_read
from ariadne.evaluation.score import ScoringContext, parse_path_tokens, score_agent_result

_STATIC = Path(__file__).parent / "static"
app = Flask(__name__, static_folder=str(_STATIC), static_url_path="/static")

_LABEL_ORDER = ["Domain", "Group", "Computer", "User"]
_PROP_KEYS = ("hasspn", "crackable", "roastable_target", "unconstraineddelegation",
              "admincount", "highvalue", "is_dc")


def _primary_label(labels) -> str:
    for lbl in _LABEL_ORDER:
        if labels and lbl in labels:
            return lbl
    return (labels or ["Base"])[0]


def _subgraph(ctx, oids):
    """Nodes + real canonical edges induced by a set of object ids."""
    oids = sorted({o for o in oids if o})
    if not oids:
        return [], []
    nrows = run_read(
        ctx.driver,
        "MATCH (n) WHERE n.objectid IN $oids "
        "RETURN n.objectid AS id, labels(n) AS labels, n.name AS name, properties(n) AS props",
        database=ctx.database, oids=oids,
    )
    nodes = []
    for r in nrows:
        name = r["name"] or r["id"]
        p = r["props"] or {}
        nodes.append({
            "id": r["id"], "name": name, "type": _primary_label(r["labels"]),
            "goal": bool(name and name.upper().startswith("DOMAIN ADMINS@")),
            "props": {k: p.get(k) for k in _PROP_KEYS if p.get(k) not in (None, False)},
        })
    erows = run_read(
        ctx.driver,
        "MATCH (a)-[r]->(b) WHERE a.objectid IN $oids AND b.objectid IN $oids "
        "RETURN a.objectid AS s, type(r) AS t, b.objectid AS d",
        database=ctx.database, oids=oids,
    )
    edges = [{"source": r["s"], "target": r["d"], "type": r["t"]} for r in erows]
    return nodes, edges


def _discovered_oids(steps, extra):
    """Every object id the run touched — tool inputs, observation targets, path."""
    found = set(extra)
    for s in steps:
        if isinstance(s.get("input"), str) and s["input"].startswith("S-1-5-"):
            found.add(s["input"])
        obs = s.get("observation")
        if isinstance(obs, list):
            for item in obs:
                if isinstance(item, dict) and item.get("objectid"):
                    found.add(item["objectid"])
        elif isinstance(obs, dict) and obs.get("objectid"):
            found.add(obs["objectid"])
    return found


def _observation_summary(step):
    """A short, human line describing what a step's tool returned."""
    obs = step.get("observation")
    action = step.get("action")
    if action == "finish":
        return "proposes the path"
    if isinstance(obs, list):
        if action == "search_node":
            return f"resolved {len(obs)} node(s)"
        return f"{len(obs)} edge(s)"
    if isinstance(obs, dict):
        hot = [k for k in ("roastable_target", "unconstraineddelegation") if obs.get(k)]
        return "read properties" + (f" — inferred step available ({', '.join(hot)})" if hot else "")
    return str(obs)[:80] if obs is not None else ""


@app.get("/")
def index():
    return send_from_directory(_STATIC, "index.html")


@app.get("/api/starts")
def api_starts():
    """Planted footholds (known answers) + a sample of random users."""
    ctx = ScoringContext.load()
    planted = run_read(
        ctx.driver,
        "MATCH (u:User) WHERE u.planted = true RETURN u.name AS name ORDER BY u.name",
        database=ctx.database,
    )
    randoms = run_read(
        ctx.driver,
        "MATCH (u:User) WHERE coalesce(u.planted,false)=false "
        "RETURN u.name AS name ORDER BY u.name LIMIT 40",
        database=ctx.database,
    )
    short = lambda n: (n or "").split("@")[0]
    return jsonify({
        "planted": [short(r["name"]) for r in planted],
        "random": [short(r["name"]) for r in randoms],
    })


@app.post("/api/run")
def api_run():
    start = (request.get_json(silent=True) or {}).get("start", "").strip()
    if not start:
        return jsonify({"error": "Pick a starting node first."}), 400

    steps: list[dict] = []
    result = run_agent(start, verbose=False, on_step=lambda s: steps.append(s))

    ctx = ScoringContext.load()
    start_oid = ctx.resolve(start)
    if start_oid is None:
        rows = run_read(ctx.driver, "MATCH (n) WHERE toUpper(n.name) STARTS WITH $p "
                        "RETURN n.objectid AS oid LIMIT 1", database=ctx.database, p=start.upper())
        start_oid = rows[0]["oid"] if rows else None

    score = score_agent_result(ctx, result, start_oid) if start_oid else {}

    # Build the proposed path (the thread), hop by hop, tagging each hop's kind.
    tokens = parse_path_tokens(result.answer, result.path_field)
    resolved = [ctx.resolve(t) for t in tokens]
    path = []
    for a, b, an, bn in zip(resolved, resolved[1:], tokens, tokens[1:]):
        kind = ctx.hop_kind(a, b) if (a and b) else None
        path.append({
            "from": a, "to": b,
            "from_name": (ctx.names.get(a) or an).split("@")[0] if a else an,
            "to_name": (ctx.names.get(b) or bn).split("@")[0] if b else bn,
            "kind": kind[0] if kind else "broken",
            "label": kind[1] if kind else None,
        })

    path_oids = [o for o in resolved if o]
    nodes, edges = _subgraph(ctx, _discovered_oids(steps, path_oids + ([start_oid] if start_oid else [])))
    steps_out = [{
        "step": s["step"], "action": s["action"], "input": s.get("input"),
        "reasoning": s.get("reasoning", ""), "summary": _observation_summary(s),
    } for s in steps]

    return jsonify({
        "start": start, "start_oid": start_oid, "answer": result.answer,
        "steps": steps_out, "nodes": nodes, "edges": edges, "path": path,
        "verdict": score,
        "telemetry": {"tool_calls": result.tool_calls, "steps": result.steps,
                      "seconds": round(result.elapsed_seconds, 1),
                      "cost_usd": round(result.cost_usd, 4)},
    })


@app.get("/api/checks")
def api_checks():
    return jsonify([{"name": n, "description": d} for n, (_f, d) in CHECKS.items()])


@app.get("/api/check/<name>")
def api_check(name):
    if name not in CHECKS:
        return jsonify({"error": f"Unknown check {name!r}."}), 404
    ctx = ScoringContext.load()
    findings = run_check(name, ctx)
    out = []
    for f in findings:
        oid = ctx.name_to_oid.get((f.subject or "").upper())
        out.append({"subject": (f.subject or "").split("@")[0], "oid": oid,
                    "detail": f.detail, "severity": f.severity, "evidence": f.evidence})
    return jsonify({"check": name, "findings": out})


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Ariadne visualiser (local web UI).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()
    print(f"\n  Ariadne visualiser -> http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
