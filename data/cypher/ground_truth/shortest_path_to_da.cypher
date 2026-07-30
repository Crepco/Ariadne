// BloodHound-equivalent shortest attack path from a starting principal to Domain
// Admins. This is the rule-based baseline: its relationship filter is exactly
// ariadne.schema.CANONICAL_EDGES — the primitives a canonical shortest-path query
// encodes, and the only edges the graph contains.
//
// Ariadne's TRUE-reachability ground truth goes further, but NOT by traversing
// more edge types: advanced tradecraft (kerberoast, unconstrained delegation,
// ADCS ESC1, credential exposure) is derived from node PROPERTIES by
// ariadne.inference, so it is not in this graph as edges at all. That is why this
// query structurally cannot find those paths, and why the gap can't be closed by
// widening the filter below. score.py builds the filter programmatically so it
// never drifts from the schema.
//
// The :Base label is carried by every node so this lookup can use an index
// instead of scanning the whole graph.
//
// Parameters:
//   $start  objectid of the starting node (e.g. a phished user)
//   $goal   objectid of the DOMAIN ADMINS group

MATCH (s:Base {objectid: $start}), (g:Base {objectid: $goal})
MATCH p = shortestPath(
  (s)-[:MemberOf|AdminTo|CanRDP|CanPSRemote|ExecuteDCOM|HasSession
      |ForceChangePassword|AllExtendedRights|AddMember
      |GenericAll|GenericWrite|WriteDacl|WriteOwner|Owns
      |DCSync*1..15]->(g)
)
RETURN [n IN nodes(p) | n.name] AS nodes,
       [r IN relationships(p) | type(r)] AS edges,
       length(p) AS hops;

// Find the DOMAIN ADMINS objectid to use as $goal:
//   MATCH (g:Group) WHERE g.name STARTS WITH 'DOMAIN ADMINS@' RETURN g.objectid;
