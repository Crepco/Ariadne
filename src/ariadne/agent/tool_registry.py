from ariadne.tools import (
    search_node,
    query_outbound_edges,
    query_inbound_edges,
    check_path_exists,
)

TOOLS = {
    "search_node": search_node,
    "query_outbound_edges": query_outbound_edges,
    "query_inbound_edges": query_inbound_edges,
    "check_path_exists": check_path_exists,
}