# Ariadne

**Can an LLM agent trace an Active Directory attack path to Domain Admin on its own — and how does it compare to BloodHound?**

Ariadne is a small, reproducible benchmark that drops a language-model agent into a graph of Active Directory (AD) misconfigurations and asks it to find a privilege-escalation path from a low-privilege account to **Domain Admin**, using only a handful of graph-query tools — exactly the exploration a human analyst does by hand in BloodHound. Every run is scored against a ground-truth shortest path, so we can measure how often the agent is *right*, how often it *hallucinates* an edge that doesn't exist, and how all of this changes as the graph grows.

> In the myth, Ariadne's thread is what lets Theseus find his way back out of the labyrinth. Here it's the question of whether an LLM can trace its own thread through the tangled graph of an AD forest.

No Windows lab required: the AD graph is generated **synthetically** in the BloodHound schema, straight into Neo4j. The agent can't tell it from a real SharpHound collection, because the structure is identical.

---

## Results

A two-model sweep (`openai/gpt-4o-mini` and `openai/gpt-4o`, temperature 0), **37 scored runs** across two graph sizes (10 planted + 3 random starts each). Advanced steps here are **inferred from properties**, not edges (see below):

| Model | Runs | Correctness | Hallucination | Beats BH | Avg tool calls | Avg cost |
| :-- | ---: | ---: | ---: | ---: | ---: | ---: |
| `openai/gpt-4o` | 11 | 100.0% | 0.0% | 4 | 5.2 | $0.031 |
| `openai/gpt-4o-mini` | 26 | 76.9% | 0.0% | 6 | 6.7 | $0.002 |

![Correctness vs. hallucination by model](results/model_comparison.png)

Overall: **83.8% correct, 0.0% hallucination**, every real path it finds is the **shortest one** (30/30 optimal). Three findings stand out:

- **It finds paths BloodHound's rule-based query structurally can't.** On the 12 cases reachable *only* through an inferred step, the agent found a real path **10 times — 83% advanced-case recall** (up from 33% before self-verification), spanning all four inference primitives: kerberoast, unconstrained delegation, ADCS ESC1, and credential exposure. These are steps the canonical query cannot follow at all, because they are not edges in the graph.
- **Self-verification eliminated hallucinations.** Making the agent run its proposed path through the `verify_path` tool before finishing drove the hallucination rate to **0%** and fixed the multi-hop kerberoast chain it used to drop the roasted node from — a rejected hop now sends it back to repair the path instead of shipping an invalid one.
- **The stronger model is worth it where budget allows.** `gpt-4o` solved **100%** of the runs it completed (vs 77% for `mini`) at ~17× the cost. Its sample is smaller — 15 of its 26 attempts were dropped as OpenRouter credit/rate-limit errors (not counted as misses), so read the 100% as a capped-N signal, not a calibrated rate.

Reproduce with `python experiments/run_benchmark.py --models openai/gpt-4o-mini openai/gpt-4o` (see [Quickstart](#quickstart)). Full numbers, per-model and per-size tables, and the failure-mode breakdown in [`results/metrics.md`](results/metrics.md).

---

## How it works

```
 data/generator/            src/ariadne/tools/      src/ariadne/agent/       src/ariadne/evaluation/
 seeded generator  ──►  Neo4j  ──►  4 query tools  ──►  ReAct loop (LLM)  ──►  hop-by-hop scoring
 (BloodHound schema)     graph                          reason→act→observe     + metrics + plots
                           │
                           └──►  ground-truth shortest path (Cypher)  =  BloodHound-equivalent baseline
```

The agent is **never shown the whole graph as text** — that would reduce the task to pattern-matching. It gets six tools and must explore:

| Tool | What it returns |
| --- | --- |
| `search_node(name_or_type)` | Resolve a user/group/computer by name or label to its object id |
| `query_outbound_edges(node)` | What this object can control / reach (`GenericAll`, `MemberOf`, `ForceChangePassword`, …) |
| `query_inbound_edges(node)` | What can control / reach this object |
| `get_node_properties(node)` | A node's **properties** — some enable *inferred* steps that are not edges |
| `check_path_exists(start, end)` | Whether a canonical-edge chain exists in the graph |
| `verify_path(names)` | Whether an ordered path is a real edge-or-inference chain to Domain Admins; names the first broken hop |

It runs a minimal **ReAct loop** (reason → call a tool → observe → repeat) and, before finishing, must run its proposed path through `verify_path` — a rejected hop sends it back to repair the path instead of shipping an invalid one. Scoring then verifies that path **hop by hop** against Neo4j: every claimed hop must be a real edge *or* a property-justified inferred step reaching Domain Admins, or it's counted as a hallucination. (This self-verification step drove the measured hallucination rate to 0%.)

**Edges vs. inference — where the agent can *genuinely* beat BloodHound.** The graph contains only *canonical* BloodHound edges (`MemberOf`, `GenericAll`, `ForceChangePassword`, …) — exactly what BloodHound's classic "shortest path to Domain Admins" query traverses, our rule-based baseline. Advanced tradecraft is deliberately **not** an edge: a kerberoastable service account is a `hasspn`+`crackable` **property**; an unconstrained-delegation host is an `unconstraineddelegation` **property**. A pure shortest-path query *structurally cannot* follow those steps — there is no edge to follow — but an agent that reads a node's properties can infer them, and the verifier accepts the step only if the property justifies it. When the agent's verified path uses such an inferred step and the canonical query finds nothing, it **`beats_bloodhound`** — and, crucially, that gap can't be closed by adding one edge type to the baseline's filter, because the step isn't in the collected graph at all. That is the honest version of the claim.

### The verified reader: checks + a grounded chat assistant

The same engine drives a practical layer that works on **real** BloodHound data too (ingest an export, then point everything at it):

- **Vulnerability checks** ([`checks.py`](src/ariadne/checks.py)) — deterministic detections (`kerberoastable_to_da`, `unconstrained_delegation`, `adcs_esc1`, `credential_exposure`, `dangerous_acls`, `nested_da`, `session_exposure`), each returning findings backed by concrete graph evidence, so they can't hallucinate. `ariadne-report` rolls them into a whole-domain audit that also flags the paths BloodHound's canonical query can't see.
- **A grounded chat assistant** ([`chat.py`](src/ariadne/chat.py), run with `ariadne-chat`) — ask in English; an LLM *routes* the question to a check, a verified path search, triage, an explanation, or a read-only Cypher query. The safety invariant: **it never asserts a path or finding the graph doesn't confirm** — every proposed path goes through the verifier, and writes are refused. The LLM routes and explains; the graph and the checks are the truth.

This is the honest framing of "AI + BloodHound": BloodHound (or the synthetic generator) supplies the graph and the deterministic queries; the LLM adds reasoning and a natural-language surface, with a verifier between it and every claim.

And you can **watch it happen**: `ariadne-web` opens a local visualiser where the agent traces its thread through the graph hop by hop — gold for canonical edges, **cyan for inferred steps BloodHound can't see**, crimson at Domain Admins — and closes with the verdict (including "Beats BloodHound").

---

## Quickstart

**Prerequisites:** Python 3.11+, a Neo4j database (a free [Neo4j Aura](https://console.neo4j.io) instance, or local Neo4j — see [`infra/neo4j/`](infra/neo4j/)), and an LLM API key ([OpenRouter](https://openrouter.ai) by default).

```bash
# 1. Install (editable). Extras: .[viz] plots, .[web] visualiser, .[gemini] Gemini backend.
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[viz,web]"

# 2. Configure credentials.
cp .env.example .env        # Windows: copy .env.example .env — then fill in NEO4J_* and OPENROUTER_API_KEYS

# 3. Get a graph into Neo4j. Either the seeded synthetic one …
python data/generator/generate.py --wipe
python data/generator/verify.py            # counts + ground-truth attack paths
#    … or ingest a real BloodHound / SharpHound export (dir, .zip, or .json):
python data/ingest/bloodhound.py --from path/to/export --wipe
#    (no real collection handy? mint a safe BloodHound-shaped sample from synthetic
#     data, then ingest it exactly like the real thing — see data/ingest/README.md)
python data/ingest/export_bloodhound.py --out /tmp/sample_export
python data/ingest/bloodhound.py --from /tmp/sample_export --wipe

# 4. Run the agent once from a planted foothold.
python run.py

# 5. Watch the agent trace its thread through the graph (visualiser at localhost:5000).
ariadne-web

# 6. Or talk to the graph: a grounded security chat assistant (every answer verified).
ariadne-chat      # e.g. "find kerberoastable paths to domain admin", "explain the first one"
ariadne-report -o audit.md   # whole-domain audit (checks + the "paths BloodHound can't see")

# 7. Run the full benchmark (sweeps graph sizes, scores every run, writes results/).
python experiments/run_benchmark.py
```

Configuration lives entirely in `.env` — see [`.env.example`](.env.example) for every option (Neo4j connection, LLM backend/model, rate limits).

---

## Repository layout

| Path | Contents |
| --- | --- |
| [`data/generator/`](data/generator/) | Seeded synthetic-graph generator + ground-truth verifier |
| [`data/ingest/`](data/ingest/) | Ingest a real BloodHound / SharpHound export into Neo4j (+ a round-trip exporter for a safe sample) |
| [`data/cypher/`](data/cypher/) | Ground-truth shortest-path Cypher (the BloodHound-equivalent baseline) |
| [`src/ariadne/tools/`](src/ariadne/tools/) | The 5 graph-query tools the agent calls |
| [`src/ariadne/agent/`](src/ariadne/agent/) | ReAct loop, prompts, and the LLM backend (OpenRouter / Gemini) |
| [`src/ariadne/evaluation/`](src/ariadne/evaluation/) | Hop-by-hop verifier, per-run logging, metrics, plots |
| `src/ariadne/inference.py` | Property-based inference rules (kerberoast, unconstrained delegation) |
| `src/ariadne/checks.py` | Deterministic vulnerability-check catalog |
| `src/ariadne/chat.py`, `report.py` | Grounded chat assistant + path explanation / triage / whole-domain audit report |
| [`src/ariadne/web/`](src/ariadne/web/) | Local visualiser (`ariadne-web`) — watch the agent trace its thread |
| [`src/ariadne/`](src/ariadne/) | Shared `config`, `db`, and `schema` modules |
| [`experiments/`](experiments/) | The benchmark runner and raw run logs |
| [`results/`](results/) | Generated metrics table + scaling plots |
| [`infra/neo4j/`](infra/neo4j/) | Optional local Neo4j via Docker (alternative to Aura) |
| [`paper/`](paper/) | Short write-up of method and results |
| [`tests/`](tests/) | `tests/unit/` offline suite + manual smoke checks |

---

## Limitations & ethics

- **Synthetic, single-model, small-sample.** The graphs come from one seeded generator; results above are a single model (`gpt-4o-mini`) at temperature 0, so the three trials per case are near-duplicates. Larger sweeps and a second model are natural next steps.
- **All data is synthetic and local.** No live network is ever touched. The graphs conform to the BloodHound schema purely so the agent faces a realistic structure; there is no collection step. Any future live-collection work would only ever run against systems one owns or is explicitly authorised to test.

## License

[MIT](LICENSE) © 2026 Hamza.
