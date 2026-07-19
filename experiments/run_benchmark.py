"""Week-3 benchmark runner.

For each graph size it:
  1. regenerates the synthetic graph into Neo4j (deterministic, seed=1337),
  2. picks start users (all planted chains + N random users),
  3. runs the agent from each start, scoring every run against the ground-truth
     BloodHound baseline, and logs real telemetry to experiments/logs/results.csv,

then prints the aggregate metrics table and renders the scaling plots. At the end
it restores the default graph so the DB is left in a known state.

Usage (repo root, venv python)::

    python experiments/run_benchmark.py                       # default sweep
    python experiments/run_benchmark.py --sizes 150 350 --random 2 --trials 1
    python experiments/run_benchmark.py --no-restore          # keep last graph
"""

from __future__ import annotations

import argparse
import os

# Cap BLAS / OpenMP thread pools BEFORE numpy or pandas load anywhere. On a
# RAM-tight laptop the default (one thread pool per core, each with its own
# buffers) can exhaust memory — the "OpenBLAS: Memory allocation failed" crash —
# especially with the Neo4j driver and LLM client also resident. Must be set
# before the first numpy import, so this stays above everything.
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import random  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

from ariadne.agent import llm  # noqa: E402
from ariadne.agent.loop import run_agent  # noqa: E402
from ariadne.db import get_driver, run_read  # noqa: E402
from ariadne.evaluation.logger import LOG_FILE, log_row, reset_log  # noqa: E402
from ariadne.evaluation.score import ScoringContext, score_agent_result  # noqa: E402

# metrics/plots pull in pandas + matplotlib (numpy). They're imported lazily at
# the end of main() so numpy isn't resident during the long agent-running phase.

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "data" / "generator" / "generate.py"
INGEST = REPO / "data" / "ingest" / "bloodhound.py"
RESULTS_DIR = REPO / "results"
LOCK = REPO / "experiments" / ".benchmark.lock"

DEFAULT_SIZES = [150, 350, 600]  # user counts -> ~200 / ~460 / ~780 nodes
DEFAULT_USERS = 300              # the repo's default graph, restored at the end


def regenerate(users: int, *, computers: int | None = None, groups: int | None = None) -> None:
    """Rebuild the graph in Neo4j via the generator subprocess (with --wipe)."""
    computers = computers if computers is not None else max(20, users // 5)
    groups = groups if groups is not None else max(15, users // 8)
    cmd = [
        sys.executable, str(GEN),
        "--users", str(users),
        "--computers", str(computers),
        "--groups", str(groups),
        "--seed", "1337",
        "--wipe",
    ]
    print(f"\n>> regenerating graph: users={users} computers={computers} groups={groups}")
    proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise RuntimeError(f"generator failed for users={users}")


def ingest_export(path: str) -> None:
    """Load a real BloodHound export into Neo4j (single graph, no size sweep)."""
    cmd = [sys.executable, str(INGEST), "--from", path, "--wipe"]
    print(f"\n>> ingesting BloodHound export: {path}")
    proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise RuntimeError(f"ingest failed for {path}")


def pick_starts(database: str, n_random: int, seed: int = 1337) -> list[dict]:
    """All planted-chain start users + N random users, each as {oid, name, kind}.

    The random cohort is chosen with a seeded Python RNG over the name-sorted
    user list — NOT Cypher's unseeded ``rand()`` — so the exact same start users
    recur across benchmark runs, keeping the whole sweep reproducible.
    """
    driver = get_driver()  # shared process-wide driver; closed at interpreter exit
    planted = run_read(
        driver,
        "MATCH (u:User) WHERE u.planted = true "
        "RETURN u.objectid AS oid, u.name AS name ORDER BY u.name",
        database=database,
    )
    pool = run_read(
        driver,
        "MATCH (u:User) WHERE coalesce(u.planted, false) = false "
        "RETURN u.objectid AS oid, u.name AS name ORDER BY u.name",
        database=database,
    )
    rng = random.Random(seed)
    randoms = pool if len(pool) <= n_random else rng.sample(pool, n_random)
    return (
        [{**r, "kind": "planted"} for r in planted]
        + [{**r, "kind": "random"} for r in randoms]
    )


def run_one(ctx: ScoringContext, start: dict, graph_size: int, max_steps: int) -> dict:
    """Run + score a single agent trial, returning a CSV row (never raises)."""
    short = start["name"].split("@")[0]
    row = {
        "model": llm.active_model(),
        "graph_size": graph_size,
        "scenario": f"{start['kind']}:{short}",
        "start_name": start["name"],
        "start_node": start["oid"],
        "goal": "DOMAIN ADMINS",
    }
    try:
        result = run_agent(start["name"], max_steps=max_steps, verbose=False)
        score = score_agent_result(ctx, result, start["oid"])
        row.update(score)
        row.update(
            tool_calls=result.tool_calls,
            steps=result.steps,
            max_steps=result.max_steps,
            time_seconds=result.elapsed_seconds,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=result.cost_usd,
            error="",
        )
    except Exception as e:  # keep the sweep alive if one run blows up
        row.update(
            proposed_path="", path_valid=False, hallucinated_edge=False, correct=False,
            declared_no_path=False, agent_hops=-1, baseline_reachable="", baseline_hops=-1,
            bloodhound_reachable="", bloodhound_hops=-1, beats_bloodhound=False,
            matches_baseline=False, optimal=False, tool_calls=0, steps=0, max_steps=max_steps,
            time_seconds=0.0, prompt_tokens=0, completion_tokens=0, cost_usd=0.0,
            error=str(e),
        )
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", type=int, nargs="+", default=DEFAULT_SIZES, help="user counts per graph")
    ap.add_argument("--random", type=int, default=3, help="random start users per graph")
    ap.add_argument("--trials", type=int, default=1, help="trials per start user")
    ap.add_argument("--models", nargs="+", default=[llm.active_model()],
                    help="one or more model ids to compare (OpenRouter slugs or a Gemini id)")
    ap.add_argument("--max-steps", type=int, default=None,
                    help="agent reasoning-step budget per run (default: the loop's MAX_STEPS)")
    ap.add_argument("--seed", type=int, default=1337, help="seed for random start-user selection")
    ap.add_argument("--from", dest="source_export", default=None,
                    help="run on a real BloodHound export (dir/zip) instead of the synthetic sweep")
    ap.add_argument("--no-restore", action="store_true", help="don't rebuild the default graph at the end")
    args = ap.parse_args()

    from ariadne.agent.loop import MAX_STEPS
    max_steps = args.max_steps if args.max_steps is not None else MAX_STEPS

    # Either sweep synthetic sizes, or run once on an ingested BloodHound export.
    if args.source_export:
        setups = [("bloodhound", lambda: ingest_export(args.source_export))]
        restore = False
    else:
        setups = [(str(u), (lambda u=u: regenerate(u))) for u in args.sizes]
        restore = not args.no_restore

    # Guard against a second benchmark running concurrently: both would wipe and
    # rewrite the SAME database and the same results.csv, clobbering each other.
    if LOCK.exists():
        print(f"A benchmark appears to be running already (lock file: {LOCK}).\n"
              f"Run only one at a time. If you're sure none is running, delete that file and retry.")
        sys.exit(1)
    LOCK.write_text(str(os.getpid()), encoding="utf-8")

    reset_log()
    t0 = time.perf_counter()
    run_idx = 0

    try:
        for _label, setup in setups:
            setup()
            ctx = ScoringContext.load()
            graph_size = len(ctx.oids)
            starts = pick_starts(ctx.database, args.random, args.seed)
            print(f"   graph_size={graph_size} nodes, {len(starts)} start users x "
                  f"{args.trials} trial(s) x {len(args.models)} model(s), max_steps={max_steps}")
            try:
                for model in args.models:
                    llm.set_model(model)
                    for start in starts:
                        for _ in range(args.trials):
                            run_idx += 1
                            row = run_one(ctx, start, graph_size, max_steps)
                            log_row(row)
                            verdict = "ERR" if row["error"] else ("OK " if row["correct"] else "MISS")
                            bh = " BEATS-BH" if row.get("beats_bloodhound") else ""
                            print(f"   [{run_idx:>3}] {verdict}  {model:<26} {row['scenario']:<26} "
                                  f"valid={row['path_valid']!s:<5} halluc={row['hallucinated_edge']!s:<5} "
                                  f"calls={row['tool_calls']} {row['time_seconds']}s{bh}")
            finally:
                ctx.close()

        print(f"\nSwept {run_idx} runs in {time.perf_counter() - t0:.0f}s.\n")

        # Deferred so pandas/matplotlib (numpy) aren't resident during the sweep.
        from ariadne.evaluation.metrics import compute_metrics, metrics_markdown
        from ariadne.evaluation.plots import make_plots

        compute_metrics()
        make_plots()
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / "metrics.md").write_text(metrics_markdown(), encoding="utf-8")
        print(f"Wrote {RESULTS_DIR / 'metrics.md'}")
        print(f"Log: {LOG_FILE}")

        if restore:
            print("\nRestoring default graph ...")
            regenerate(DEFAULT_USERS, computers=60, groups=40)
            print("Default graph restored.")
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
