from ariadne.agent.loop import run_agent
from ariadne.evaluation.score import score_run
from ariadne.evaluation.logger import log_run


def main():
    start = "PLANT_A_START"

    print("=" * 50)
    print("Running Ariadne Agent")
    print("=" * 50)

    result = run_agent(start)

    print("\nAgent Output:")
    print(result)

    # Later you'll replace these with the actual values returned by the agent
    score = score_run(
        "S-1-5-21-3653228291-3290358181-2571306751-900001",
        "S-1-5-21-3653228291-3290358181-2571306751-512",
    )

    log_run(
    model="Gemini",
    scenario="PLANT_A",
    graph_size=412,
    start_node=start,
    goal="DOMAIN ADMINS",
    proposed_path=str(result),
    tool_calls=2,
    time_seconds=0,
    path_valid=score["path_valid"],
    matches_baseline=False,
    hallucinated_edge=score["hallucinated_edge"],
)

    print("\nRun completed.")


if __name__ == "__main__":
    main()