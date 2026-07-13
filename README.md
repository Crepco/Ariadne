# Ariadne

**Can an LLM agent trace an Active Directory attack path to Domain Admin on its own — and how does it compare to BloodHound?**

Ariadne is a small, reproducible benchmark that drops a language-model agent into a graph of Active Directory (AD) misconfigurations and asks it to find a privilege-escalation path from a low-privilege account to **Domain Admin**, using only a handful of graph-query tools — exactly the exploration a human analyst does by hand in BloodHound. Every run is scored against a ground-truth shortest path, so we can measure how often the agent is *right*, how often it *hallucinates* an edge that doesn't exist, and how all of this changes as the graph grows.

> In the myth, Ariadne's thread is what lets Theseus find his way back out of the labyrinth. Here it's the question of whether an LLM can trace its own thread through the tangled graph of an AD forest.

No Windows lab required: the AD graph is generated **synthetically** in the BloodHound schema, straight into Neo4j. The agent can't tell it from a real SharpHound collection, because the structure is identical.

---

## Results

A pilot sweep with `openai/gpt-4o-mini` (temperature 0), 104 valid runs across three graph sizes:

| Nodes | Correctness | Hallucination | Avg tool calls | Avg time |
| ---: | ---: | ---: | ---: | ---: |
| 210 | 75.0% | 5.6% | 5.7 | 17.8s |
| 409 | 58.3% | 2.8% | 6.1 | 19.8s |
| 674 | 37.5% | 0.0% | 8.0 | 24.4s |

![Scaling behaviour](results/scaling.png)

Two findings stand out:

- **Correctness falls sharply as the graph grows** (75% → 37.5%), while exploration cost rises. Against BloodHound — which finds a path whenever one exists — the agent solved only ~47% of the genuinely reachable cases (missed 44 of 83).
- **But the agent is honest when it answers:** the hallucination rate is low and *decreases* with size (down to 0%). On larger graphs it fails by giving up or missing the path, not by fabricating edges.

Reproduce with `python experiments/run_benchmark.py` (see [Quickstart](#quickstart)). Full numbers in [`results/metrics.md`](results/metrics.md).

---

## How it works

```
 data/generator/            src/ariadne/tools/      src/ariadne/agent/       src/ariadne/evaluation/
 seeded generator  ──►  Neo4j  ──►  4 query tools  ──►  ReAct loop (LLM)  ──►  hop-by-hop scoring
 (BloodHound schema)     graph                          reason→act→observe     + metrics + plots
                           │
                           └──►  ground-truth shortest path (Cypher)  =  BloodHound-equivalent baseline
```

The agent is **never shown the whole graph as text** — that would reduce the task to pattern-matching. It gets four tools and must explore:

| Tool | What it returns |
| --- | --- |
| `search_node(name_or_type)` | Resolve a user/group/computer by name or label to its object id |
| `query_outbound_edges(node)` | What this object can control / reach (`GenericAll`, `MemberOf`, `ForceChangePassword`, …) |
| `query_inbound_edges(node)` | What can control / reach this object |
| `check_path_exists(start, end)` | Whether a chain actually exists in the graph |

It runs a minimal **ReAct loop** (reason → call a tool → observe → repeat) and finishes by proposing an ordered attack path. Scoring then verifies that path **edge by edge** against Neo4j: every claimed hop must be a real relationship reaching Domain Admins, or it's counted as a hallucination. The same graph's Cypher `shortestPath` is the BloodHound-equivalent answer key.

---

## Quickstart

**Prerequisites:** Python 3.11+, a Neo4j database (a free [Neo4j Aura](https://console.neo4j.io) instance, or local Neo4j — see [`infra/neo4j/`](infra/neo4j/)), and an LLM API key ([OpenRouter](https://openrouter.ai) by default).

```bash
# 1. Install (editable). Add extras as needed: .[viz] for plots, .[gemini] for the Gemini backend.
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[viz]"

# 2. Configure credentials.
cp .env.example .env        # then fill in NEO4J_* and OPENROUTER_API_KEYS

# 3. Generate the synthetic graph into Neo4j (deterministic, seed=1337).
python data/generator/generate.py --wipe
python data/generator/verify.py            # counts + ground-truth attack paths

# 4. Run the agent once from a planted foothold.
python run.py

# 5. Run the full benchmark (sweeps graph sizes, scores every run, writes results/).
python experiments/run_benchmark.py --sizes 150 350 600 --random 5
```

Configuration lives entirely in `.env` — see [`.env.example`](.env.example) for every option (Neo4j connection, LLM backend/model, rate limits).

---

## Repository layout

| Path | Contents |
| --- | --- |
| [`data/generator/`](data/generator/) | Seeded synthetic-graph generator + ground-truth verifier |
| [`data/cypher/`](data/cypher/) | Ground-truth shortest-path Cypher (the BloodHound-equivalent baseline) |
| [`src/ariadne/tools/`](src/ariadne/tools/) | The 4 graph-query tools the agent calls |
| [`src/ariadne/agent/`](src/ariadne/agent/) | ReAct loop, prompts, and the LLM backend (OpenRouter / Gemini) |
| [`src/ariadne/evaluation/`](src/ariadne/evaluation/) | Hop-by-hop scoring, per-run logging, metrics, plots |
| [`src/ariadne/`](src/ariadne/) | Shared `config`, `db`, and `schema` modules |
| [`experiments/`](experiments/) | The benchmark runner and raw run logs |
| [`results/`](results/) | Generated metrics table + scaling plots |
| [`infra/neo4j/`](infra/neo4j/) | Optional local Neo4j via Docker (alternative to Aura) |
| [`paper/`](paper/) | Short write-up of method and results |
| [`tests/`](tests/) | Manual per-component smoke checks |

---

## Limitations & ethics

- **Synthetic, single-model, small-sample.** The graphs come from one seeded generator; results above are a single model (`gpt-4o-mini`) at temperature 0, so the three trials per case are near-duplicates. Larger sweeps and a second model are natural next steps.
- **All data is synthetic and local.** No live network is ever touched. The graphs conform to the BloodHound schema purely so the agent faces a realistic structure; there is no collection step. Any future live-collection work would only ever run against systems one owns or is explicitly authorised to test.

## License

[MIT](LICENSE) © 2026 Hamza.
