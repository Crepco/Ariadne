"""Single agent run against the current graph (a quick smoke test / demo).

For the full multi-size benchmark use experiments/run_benchmark.py.
"""

from ariadne.agent.llm import active_model
from ariadne.agent.loop import run_agent
from ariadne.evaluation.logger import log_row
from ariadne.evaluation.score import ScoringContext, score_agent_result
from ariadne.tools import search_node


def main():
    start_name = "PLANT_A_START"

    print("=" * 50)
    print("Running Ariadne Agent")
    print("=" * 50)

    result = run_agent(start_name)

    print("\nAgent Output:")
    print(result.answer)

    ctx = ScoringContext.load()
    try:
        start_oid = ctx.resolve(start_name) or search_node(start_name)[0]["objectid"]
        score = score_agent_result(ctx, result, start_oid)

        log_row(
            {
                "model": active_model(),
                "graph_size": len(ctx.oids),
                "scenario": "single:PLANT_A_START",
                "start_name": start_name,
                "start_node": start_oid,
                "goal": "DOMAIN ADMINS",
                **score,
                "tool_calls": result.tool_calls,
                "steps": result.steps,
                "time_seconds": result.elapsed_seconds,
                "error": "",
            }
        )
    finally:
        ctx.close()

    print(
        f"\nRun completed: correct={score['correct']}, "
        f"valid_path={score['path_valid']}, hallucinated={score['hallucinated_edge']}, "
        f"{result.tool_calls} tool calls, {result.elapsed_seconds:.1f}s."
    )


if __name__ == "__main__":
    main()
