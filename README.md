# Ariadne

**Autonomous LLM agents for Active Directory attack-path discovery — evaluated on synthetic BloodHound graph data.**

> In the myth, Ariadne's thread is what lets Theseus find his way out of the labyrinth. This project asks whether an LLM agent can trace its own thread through the tangled graph of an Active Directory (AD) forest — from a low-privilege foothold all the way to Domain Admin — and how it stacks up against BloodHound's rule-based queries.

---

## The one-sentence version

Build an AI agent that explores a graph of Active Directory misconfigurations and figures out an attack path to Domain Admin on its own, then measure how well it does against BloodHound's rule-based approach — using fake-but-realistic graph data so we never run a single Windows VM.

## The research question

> Given the same graph BloodHound uses, can a modern AI agent do the human's reasoning part — exploring the graph step by step and discovering a valid attack path on its own — and how does it compare to BloodHound on **accuracy**, **speed**, and how often it **invents paths that don't actually exist**?

## Why no Windows lab

The agent never touches a live Windows network. It only ever reasons over the **graph** — the nodes and edges stored in a database. Normally an entire Windows/GOAD lab exists just to *produce* that graph. By generating a structurally realistic graph **directly** into Neo4j (synthetic BloodHound data), the whole Windows layer disappears: no domain controller, no 24 GB of RAM — just a lightweight database and Python. The agent can't tell synthetic data from a real collection, because the schema is identical.

---

## System architecture

Data flows top to bottom:

```
  1. DBCreator (Python)            generates a synthetic AD graph
             │
             ▼
  2. Neo4j (Docker container)      stores users, groups, computers + relationship edges
             │
             ▼
  3. Query-tool layer (Python)     exposes 4 graph-query tools the agent can call
             │
             ▼
  4. LLM agent (ReAct loop)        reasons step by step, proposes an attack path
```

Running alongside for scoring: a set of **Cypher queries** that compute the true shortest paths (the answer key), and a **logger** that records every agent run.

### The agent's four tools

The agent is **not** handed the whole graph as text — that would reduce the task to pattern-matching. Instead it explores, exactly like a human clicking through BloodHound:

| Tool | What it returns |
| --- | --- |
| `query_outbound_edges(node)` | What this object can control / reach (full-control, member-of, reset-password, …) |
| `query_inbound_edges(node)` | What can control / reach this object |
| `search_node(name_or_type)` | Find a user, group, or computer by name or type |
| `check_path_exists(start, end)` | Verify whether a proposed chain actually exists (agent self-check + scoring) |

---
## Goals

- Build an autonomous LLM agent capable of exploring an Active Directory attack graph.
- Compare reasoning-based exploration against BloodHound's rule-based path discovery.
- Measure hallucinations during graph reasoning.
- Evaluate how graph size affects reasoning quality.
- Provide a reproducible benchmark for evaluating AI agents on graph-search problems.
---

## Repository layout

| Path | Purpose |
| --- | --- |
| [`docs/`](docs/) | Project plan and design notes |
| [`infra/neo4j/`](infra/neo4j/) | Running Neo4j Community Edition in Docker |
| [`data/generator/`](data/generator/) | DBCreator synthetic-graph generator (michiellemmens fork) |
| [`data/cypher/`](data/cypher/) | Ground-truth shortest-path queries + planted misconfiguration chains |
| [`data/graphs/`](data/graphs/) | Generated / exported graph snapshots (git-ignored) |
| [`src/ariadne/tools/`](src/ariadne/tools/) | The 4 graph-query tools (Cypher wrapped as callable functions) |
| [`src/ariadne/agent/`](src/ariadne/agent/) | The ReAct loop and LLM access |
| [`src/ariadne/evaluation/`](src/ariadne/evaluation/) | Scoring, logging, metrics |
| [`experiments/`](experiments/) | Run configs and raw per-run logs |
| [`results/`](results/) | Figures and tables for the write-up |
| [`paper/`](paper/) | The short paper |

---

## Metrics (the results table)

| Metric | Meaning |
| --- | --- |
| Path-correctness rate | % of runs where the proposed path is verified as real in the graph |
| Hallucination rate | % of runs proposing an edge or hop that does not exist |
| Time-to-solution | Wall-clock time to the final answer |
| Tool-call efficiency | Number of queries used to reach a correct answer |
| Scaling behaviour | How correctness and time change as the graph grows (300 → 2,000+ nodes) |
| Gap vs. BloodHound | Cases where the agent finds paths BloodHound misses, or vice versa |

---

## Build plan (laptop-friendly, ~2.5–3 week solo sprint)

**Week 1 — Data + baseline**
- Run Neo4j in Docker; connect the DBCreator fork.
- Generate a synthetic graph (start at 300–500 nodes); optionally plant 2–3 misconfiguration chains.
- Write Cypher shortest-path queries → the ground-truth answer key / BloodHound-equivalent baseline.

**Week 2 — Build the agent**
- Implement the 4 graph-query tools; test each in isolation.
- Build the ReAct loop, connect one LLM, solve the simplest known path first.
- Add automated logging (tool calls, final path, time, correctness).

**Week 3 — Benchmark + write-up**
- Repeated trials across graph sizes; optionally a second model.
- Score everything; build the comparison-vs-BloodHound table and plots.
- Draft the short paper and package a reproducible artifact.

---

## Tech stack

- **Graph DB:** Neo4j Community Edition (Docker)
- **Synthetic data:** DBCreator (michiellemmens fork) — Python 3.7+, `neo4j` driver
- **Agent:** Python 3, minimal custom ReAct loop, native tool-use API
- **LLM access:** Anthropic API (Claude) — the latest Claude models; optionally a second provider for comparison
- **Ground truth / scoring:** Cypher shortest-path queries
- **Analysis:** pandas + matplotlib
- **Paper:** LaTeX (IEEE template) or Markdown

---

## Ethics

All experiments use **synthetic, locally-generated** data conforming to the BloodHound schema. There is no live network involved. If a real single-DC collection step is ever added for authenticity, collection tooling is only ever run against an environment we own or are explicitly authorised to test.

> **Status:** scaffolding only — folder structure and READMEs are in place; no implementation code yet. See each directory's README for what goes there.
