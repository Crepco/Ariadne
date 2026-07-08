# infra/neo4j/

Runs **Neo4j Community Edition** as a single Docker container — the graph database that stores the synthetic AD forest (users, groups, computers, and the relationship edges between them). This is the only piece of "infrastructure"; it replaces the entire Windows/GOAD lab.

## What lives here

- `docker-compose.yml` — *(to add)* single-service Neo4j definition: exposes the Bolt port (`7687`) for the Python driver and the browser UI (`7474`), sets the initial password, and mounts local volumes for `data/`, `logs/`, `import/`, `plugins/`.

Those mounted volume directories are git-ignored (see the root `.gitignore`) so database contents never get committed.

## Planned usage

1. `docker compose up -d` from this directory.
2. Open the Neo4j Browser at http://localhost:7474 and set/confirm the password.
3. Point `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in your `.env` at this instance.
4. Run the DBCreator generator ([`../../data/generator/`](../../data/generator/)) to fill it with a synthetic graph.

## Notes

- Community Edition is enough — no clustering or enterprise features needed.
- Neo4j + a Python script is light on RAM; a few GB free is plenty.
- If the DBCreator fork needs a specific Neo4j major version, pin the image tag here and note it in the compose file.
