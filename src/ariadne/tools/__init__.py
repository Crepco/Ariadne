from .tools import (
    search_node,
    query_outbound_edges,
    query_inbound_edges,
    get_node_properties,
    check_path_exists,
    verify_path,
)

TOOLS = {
    "search_node": search_node,
    "query_outbound_edges": query_outbound_edges,
    "query_inbound_edges": query_inbound_edges,
    "get_node_properties": get_node_properties,
    "check_path_exists": check_path_exists,
    "verify_path": verify_path,
}