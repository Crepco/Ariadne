from ariadne.evaluation import score_run
from ariadne.tools import search_node

start = search_node("PLANT_A_START")[0]["objectid"]
goal = search_node("DOMAIN ADMINS")[0]["objectid"]

result = score_run(start, goal)

print(result)