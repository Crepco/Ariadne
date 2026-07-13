# infra/neo4j/

**Optional** local Neo4j via Docker — an alternative to a cloud [Neo4j Aura](https://console.neo4j.io)
instance. Either works; the rest of the project only needs a reachable Bolt endpoint and the
credentials in `.env`.

`docker-compose.yml` runs a single Neo4j Community container, exposing the Bolt port (`7687`)
for the Python driver and the browser UI (`7474`).

## Usage

```bash
docker compose up -d          # from this directory
```

Then point your `.env` at it:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123     # matches NEO4J_AUTH in docker-compose.yml
NEO4J_DATABASE=neo4j
```

Open http://localhost:7474 to browse the graph. Then generate data with
[`../../data/generator/`](../../data/generator/).

## Notes

- Community Edition is plenty — no clustering or enterprise features are used.
- Change the password in `docker-compose.yml` (`NEO4J_AUTH`) before exposing this anywhere.
- Prefer zero local setup? Use Aura Free instead and skip this entirely.
