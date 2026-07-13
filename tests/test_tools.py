from ariadne.tools import (
    search_node,
    query_outbound_edges,
    query_inbound_edges,
    check_path_exists,
)

# Search
user = search_node("PLANT_A_START")
print(user)

oid = user[0]["objectid"]

print("\nOutbound Edges:")
print(query_outbound_edges(oid))

print("\nInbound Edges:")
print(query_inbound_edges(oid))


print("\nChecking Path:")

goal = search_node("DOMAIN ADMINS")[0]["objectid"]

print(
    check_path_exists(
        oid,
        goal
    )
)