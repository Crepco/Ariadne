// BloodHound-equivalent shortest attack path from a starting principal to Domain
// Admins. This is the rule-based baseline: its relationship filter is exactly
// ariadne.schema.CANONICAL_EDGES (the primitives a canonical shortest-path query
// encodes). The agent — and Ariadne's TRUE-reachability ground truth — traverse a
// wider set (schema.TRAVERSABLE_EDGES = canonical + ADVANCED_EDGES such as
// Kerberoastable), so the agent can find real paths this query cannot. score.py
// builds both filters programmatically so they never drift from the schema.
//
// Parameters:
//   $start  objectid of the starting node (e.g. a phished user)
//   $goal   objectid of the DOMAIN ADMINS group

MATCH (s {objectid: $start}), (g {objectid: $goal})
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
