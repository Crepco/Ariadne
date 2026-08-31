"""Deliberately narrow opus-4-8 subset: only the 2 cheapest-observed real starts.

claude-opus-4-8 costs ~25-50x haiku's rate per run on this dense real graph
(confirmed: $1.70 for the single easiest case, ~313k prompt tokens for 16 tool
calls — extended-thinking traces resent every turn compound fast). The 4 hard
multi-hop/no-path cases (catelyn, robb, arya, hodor) hit the 35-step cap on
EVERY other model tested, so at opus's multiplier each could plausibly run
$5-10+. This script deliberately runs only lord.varys (known ~$1.70-2) and
jaime.lannister (moderate on every other model) to keep total spend bounded.

Uses the same resumable (model, start) skip + log_row schema as run_real.py,
so results merge cleanly and metrics.md/plots pick this up on next regenerate.

    PYTHONPATH=src python experiments/run_opus_subset.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from ariadne.agent import llm  # noqa: E402
from ariadne.evaluation.logger import LOG_FILE, log_row  # noqa: E402
from ariadne.evaluation.score import ScoringContext  # noqa: E402
from ariadne.tools import search_node  # noqa: E402
from run_benchmark import run_one  # noqa: E402

MODEL = "claude-opus-4-8"
STARTS = [
    ("lord.varys@sevenkingdoms.local",      "path"),
    ("jaime.lannister@sevenkingdoms.local", "control"),
]
MAX_STEPS = 35
INFRA_RETRIES = 2   # opus is expensive; don't burn money re-retrying a bad case


def done_pairs() -> set[tuple[str, str]]:
    done: set[tuple[str, str]] = set()
    if LOG_FILE.exists():
        with open(LOG_FILE, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if not r.get("error"):
                    done.add((r["model"], r["start_name"]))
    return done


def main() -> None:
    ctx = ScoringContext.load()
    graph_size = len(ctx.oids)
    done = done_pairs()

    llm.set_model(MODEL)
    for name, kind in STARTS:
        if (MODEL, name) in done:
            print(f"skip (done): {name}", flush=True)
            continue
        oid = ctx.resolve(name)
        if not oid:
            hits = search_node(name)
            oid = hits[0]["objectid"] if hits else None
        if not oid:
            print(f"WARN: cannot resolve {name}; skipping")
            continue
        print(f"RUN  {MODEL}  {name} ({kind}) ...", flush=True)
        row = run_one(ctx, {"name": name, "oid": oid, "kind": kind}, graph_size,
                       MAX_STEPS, infra_retries=INFRA_RETRIES)
        log_row(row)
        print(f"    -> correct={row['correct']} valid={row['path_valid']} "
              f"halluc={row['hallucinated_edge']} calls={row.get('tool_calls')} "
              f"{row.get('time_seconds')}s cost=${row.get('cost_usd')} "
              f"err={bool(row['error'])}", flush=True)
    ctx.close()
    print("opus subset DONE", flush=True)


if __name__ == "__main__":
    main()
