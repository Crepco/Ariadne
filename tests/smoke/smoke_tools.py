"""Manual smoke check: the six graph tools against a live Neo4j.

Needs a populated graph (``python data/generator/generate.py --wipe``) and a
filled-in ``.env``. Run from the repo root::

    python tests/smoke/smoke_tools.py
"""

from ariadne.agent.loop import _call_tool
from ariadne.tools import (
    TOOLS,
    check_path_exists,
    get_node_properties,
    query_inbound_edges,
    query_outbound_edges,
    search_node,
    verify_path,
)

START = "PLANT_A_START"

user = search_node(START)
print(f"search_node({START!r}):")
print(user)
if not user:
    raise SystemExit(f"{START} not found — generate a graph first "
                     f"(python data/generator/generate.py --wipe).")

oid = user[0]["objectid"]

print("\nOutbound edges:")
print(query_outbound_edges(oid))

print("\nInbound edges:")
print(query_inbound_edges(oid))

print("\nProperties (inferred steps live here, not in the edges):")
print(get_node_properties(oid))

goal = search_node("DOMAIN ADMINS")[0]["objectid"]

print("\ncheck_path_exists (two arguments, called directly):")
print(check_path_exists(oid, goal))

# The same tool as the AGENT reaches it. This is the path that was broken: the
# dispatcher passed one positional argument, so every agent-side call to a
# two-argument tool raised TypeError and was swallowed as an opaque tool error.
print("\ncheck_path_exists (through the agent's dispatcher, object input):")
print(_call_tool(TOOLS["check_path_exists"], "check_path_exists",
                 {"start_objectid": oid, "goal_objectid": goal}))

print("\ncheck_path_exists (through the dispatcher with the WRONG shape — "
      "should explain itself, not blow up):")
print(_call_tool(TOOLS["check_path_exists"], "check_path_exists", oid))

print("\nverify_path on a deliberately bogus one-hop path (should be rejected):")
print(verify_path([START, "DOMAIN ADMINS"]))
