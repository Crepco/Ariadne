"""Resumable multi-model benchmark on the already-ingested REAL GOAD forest.

Unlike run_benchmark.py (which regenerates synthetic graphs), this runs against
whatever graph is currently in Neo4j — here, the merged GOAD-Light 2-domain
forest ingested from the real SharpHound/BloodHound-CE export.

Resumable: each (model, start) pair already present in results.csv is skipped,
so a laptop sleep/shutdown mid-run continues rather than restarting. Start users
are chosen deliberately (documented) to cover real path-finding cases plus
no-path controls (to test hallucination), rather than random sampling.

After all runs it regenerates results/metrics.md + results/*.png and archives
the raw CSV under results/runs/.

    PYTHONPATH=src python experiments/run_real.py
"""
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import os  # noqa: E402

# Route the "openrouter" gateway backend at OpenAI's own API directly (separate
# billing from OpenRouter, which is card-blocked for this account). Must happen
# before `llm` is imported: _OPENROUTER_KEYS / _OPENROUTER_BASE_URL are read
# from the environment at module-import time, not per-call.
if os.getenv("OPENAI_API_KEY"):
    os.environ["OPENROUTER_API_KEYS"] = os.environ["OPENAI_API_KEY"]  # override, not
    os.environ["OPENROUTER_BASE_URL"] = "https://api.openai.com/v1/chat/completions"  # fallback

from ariadne.agent import llm  # noqa: E402
from ariadne.evaluation.logger import LOG_FILE, log_row  # noqa: E402
from ariadne.evaluation.score import ScoringContext  # noqa: E402
from ariadne.tools import search_node  # noqa: E402
from run_benchmark import run_one  # noqa: E402

MODELS = [
    "gemini-flash-lite-latest",                  # Google, free tier (proven reliable)
    "gpt-4o-mini",                                # OpenAI direct billing, paid ($5 loaded)
    "gpt-4o",                                     # OpenAI direct billing, full-size flagship
    "claude-haiku-4-5",                           # Anthropic direct billing, paid
    # gemini-2.5-flash's free allowance is too small for even one run (exhausted
    # after a single call, confirmed twice); OpenRouter's free Nemotron/GLM models
    # are on a shared daily pool that's stayed exhausted across multiple checks.
    # Uncomment and re-run (resumable — skips completed rows) once available:
    # "gemini-2.5-flash",
    # "nvidia/nemotron-3-super-120b-a12b:free",
    # "nvidia/nemotron-3-ultra-550b-a55b:free",
]

# gpt-4o-mini / gpt-4o have no "/" in their names, so llm._infer_provider()
# would otherwise route them to the Gemini backend by default. Force them
# through the (now OpenAI-pointed) gateway backend instead.
MODEL_PROVIDERS = {"gpt-4o-mini": "openrouter", "gpt-4o": "openrouter"}

# (start user, category). Path cases have a real route to a Domain Admins group;
# controls do not (they test whether the model hallucinates a path).
STARTS = [
    ("lord.varys@sevenkingdoms.local",          "path"),    # GenericAll -> Domain Admins (privesc)
    ("catelyn.stark@north.sevenkingdoms.local", "path"),    # multi-hop -> north Domain Admins
    ("robb.stark@north.sevenkingdoms.local",    "path"),    # multi-hop -> north Domain Admins
    ("jaime.lannister@sevenkingdoms.local",     "control"), # chain reaches DC, not DA group
    ("arya.stark@north.sevenkingdoms.local",    "control"), # low-priv, no path
    ("hodor@north.sevenkingdoms.local",         "control"), # low-priv, no path
]
MAX_STEPS = 35          # dense real graph needs room; 15 caused "max steps exceeded"
INFRA_RETRIES = 3


def done_pairs() -> set[tuple[str, str]]:
    done: set[tuple[str, str]] = set()
    if LOG_FILE.exists():
        with open(LOG_FILE, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if not r.get("error"):          # only successful runs count as done;
                    done.add((r["model"], r["start_name"]))  # errored ones retry on resume
    return done


def main() -> None:
    ctx = ScoringContext.load()
    graph_size = len(ctx.oids)

    starts = []
    for name, kind in STARTS:
        oid = ctx.resolve(name)
        if not oid:
            hits = search_node(name)
            oid = hits[0]["objectid"] if hits else None
        if not oid:
            print(f"WARN: cannot resolve {name}; skipping")
            continue
        starts.append({"name": name, "oid": oid, "kind": kind})

    done = done_pairs()
    total = len(MODELS) * len(starts)
    idx = 0
    t0 = time.perf_counter()
    try:
        for model in MODELS:
            llm.set_model(model, provider=MODEL_PROVIDERS.get(model))
            for st in starts:
                idx += 1
                if (model, st["name"]) in done:
                    print(f"[{idx}/{total}] skip (done): {model}  {st['name']}", flush=True)
                    continue
                print(f"[{idx}/{total}] RUN  {model}  {st['name']} ({st['kind']}) ...", flush=True)
                row = run_one(ctx, st, graph_size, MAX_STEPS, infra_retries=INFRA_RETRIES)
                log_row(row)
                print(f"    -> correct={row['correct']} valid={row['path_valid']} "
                      f"halluc={row['hallucinated_edge']} calls={row.get('tool_calls')} "
                      f"{row.get('time_seconds')}s err={bool(row['error'])}", flush=True)
    finally:
        ctx.close()

    print("\nAll runs complete. Regenerating metrics + plots ...", flush=True)
    from ariadne.evaluation.metrics import compute_metrics, metrics_markdown
    from ariadne.evaluation.plots import make_plots

    compute_metrics()
    make_plots()
    results = REPO / "results"
    results.mkdir(exist_ok=True)
    (results / "metrics.md").write_text(metrics_markdown(), encoding="utf-8")

    # archive raw CSV + provenance
    runs_dir = results / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base = runs_dir / f"{stamp}-real-goad"
    if LOG_FILE.exists():
        base.with_suffix(".csv").write_text(LOG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        base.with_suffix(".json").write_text(json.dumps({
            "timestamp_utc": stamp,
            "dataset": "real GOAD-Light 2-domain forest (merged CE export)",
            "graph_nodes": graph_size,
            "models": MODELS,
            "starts": STARTS,
            "max_steps": MAX_STEPS,
            "wall_seconds": round(time.perf_counter() - t0, 1),
        }, indent=2), encoding="utf-8")
    print(f"DONE. metrics.md + plots written; archived {base.with_suffix('.csv').name}", flush=True)


if __name__ == "__main__":
    main()
