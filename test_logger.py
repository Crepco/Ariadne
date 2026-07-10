from ariadne.evaluation import log_run

log_run(
    model="Gemini",
    scenario="Plant A",
    graph_size=412,
    start_node="PLANT_A_START",
    goal="DOMAIN ADMINS",
    proposed_path="START -> VICTIM -> MIDGROUP -> DOMAIN ADMINS",
    tool_calls=4,
    time_seconds=2.18,
    path_valid=True,
    matches_baseline=True,
    hallucinated_edge=False,
)