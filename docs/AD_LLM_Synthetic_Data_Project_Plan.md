# Autonomous LLM Agents for Active Directory Attack-Path Discovery

**A no-Windows, laptop-friendly build using synthetic BloodHound graph data.**

> This document explains the full project — first in plain language, then in technical
> depth — and gives a revised build plan that removes the heavy Windows / GOAD lab
> entirely. Instead of running a real Active Directory forest (which needs a powerful
> PC), you generate **synthetic AD graph data** directly into a lightweight database.
> Everything here runs comfortably on a normal laptop.

> **The one-sentence version**
> Build an AI agent that explores a graph of Active Directory misconfigurations and
> figures out an attack path to Domain Admin on its own, then measure how well it does
> against BloodHound's rule-based approach — using fake-but-realistic graph data so you
> never need to run a single Windows virtual machine.

---

## Part 1 — The Big Picture (Plain Language)

### 1.1 What is Active Directory?

Active Directory (AD) is the system almost every company uses to manage its network.
Think of it as the company's master directory: every employee account, every computer,
every group ('Finance', 'IT Admins'), and the rules about who can access or control
what. When you log into your work computer, AD is what checks your identity and decides
what you're allowed to touch.

### 1.2 What is an 'attack path'?

Over years of use, AD collects small mistakes: an ordinary user who was accidentally
given the power to reset a manager's password, a service account with a weak password, a
group that's nested inside a more powerful group by accident. Each mistake alone looks
harmless.

An **attack path** is a chain of these small mistakes that, linked together, lets an
attacker climb from a low-level account all the way up to **Domain Admin** (total control
of the company network). Picture a burglar who finds an unlocked window, which leads to a
room with a spare key, which opens a cabinet holding the master keys to the whole
building. No single step is dramatic — the chain is what's dangerous.

### 1.3 What does BloodHound already do?

BloodHound is the industry-standard tool for this. It collects all the AD relationships
and turns them into a **graph** — dots (users, computers, groups) connected by arrows
('can reset password of', 'is a member of', 'has full control over'). It then runs
pre-written queries like 'show me the shortest path to Domain Admin' and draws the
dangerous chains for you.

The catch: BloodHound is **rule-based**. It finds exactly what its built-in queries are
written to look for. If an attack path has an unusual shape that nobody wrote a query for,
BloodHound may not surface it — a human analyst still has to stare at the graph and reason
through the creative, non-obvious chains.

### 1.4 What's new in this project?

> **The research question**
> Given the same graph BloodHound uses, can a modern AI agent do the human's reasoning
> part — exploring the graph step by step and discovering a valid attack path on its own
> — and how does it compare to BloodHound on **accuracy**, **speed**, and how often it
> **invents paths that don't actually exist**?

That comparison — **AI agent vs. rule-based tool, on identical data** — is the measurable
result that makes this a real paper rather than just a demo.

---

## Part 2 — The Key Insight That Saves Your Laptop

> **Why you don't need Windows at all**
> The AI agent never touches a live Windows network. It only ever reasons over the
> **graph** — the dots and arrows stored in a database. In a normal setup, a whole Windows
> lab exists just to *produce* that graph. But if you can create a realistic graph
> *directly*, the entire Windows layer disappears. No domain controller, no GOAD, no
> 24 GB of RAM — just a lightweight database and a Python script.

This is **Option 1: synthetic BloodHound data**. You use a generator that fills a database
with fake but structurally realistic AD data — thousands of users, groups, computers, and
crucially the attack-path-relevant relationships (full-control rights, group memberships,
password-reset rights, and so on) — all matching BloodHound's real data format. Your agent
can't tell the difference between this and a graph collected from a real company, because
the structure is identical.

---

## Part 3 — How the Synthetic Data Works

### 3.1 The generator: DBCreator

The standard tool is **DBCreator** from the BloodHound-Tools project. It's a small Python
script that connects to a Neo4j database and generates a randomized AD dataset directly
inside it — no Windows, no data collection step. You control the size (e.g. 500 nodes,
2,000 nodes) and it builds the users, groups, computers, and the relationship edges
between them.

> **Important practical warning (read before Day 1)**
> The original DBCreator has a known bug in its `generate` command that many people hit.
> The widely-used fix is a maintained fork (search GitHub for **michiellemmens/DBCreator**),
> which resolves the error. Use that fork, or keep it as a fallback if the original throws
> errors. Either way it needs Python 3.7+, the `neo4j` driver, and a running Neo4j
> instance.

### 3.2 The one limitation, and why it's fine

DBCreator generates **random** relationships, so you don't get to hand-pick 'the answer is
path X' in advance. That sounds like a problem but isn't — because you compute the
ground-truth answer *after* generation, directly from the graph, using the same Cypher
queries BloodHound itself uses (e.g. shortest path from a chosen starting user to any
Domain Admin). That query result **is** your answer key. If anything, random paths are
better than hand-tuned ones because they aren't accidentally biased to be easy.

### 3.3 Optional: planting specific misconfigurations

If you want to test whether the agent handles *specific* reasoning patterns (say, a
Kerberoasting hop or a nested-group trap), you can write a few lines of Cypher to insert
those exact edges into the generated graph. This gives you a hybrid: realistic bulk data
from DBCreator, plus a handful of deliberately planted chains whose answers you already
know. Recommended, but not required for a first result.

---

## Part 4 — System Architecture

The whole system is four light pieces. Data flows top to bottom:

```
1. DBCreator (Python script)         generates a synthetic AD graph
            │
            ▼
2. Neo4j graph database (Docker)     stores users, groups, computers + relationship edges
            │
            ▼
3. Query-tool layer (Python)         exposes 4 graph-query tools the agent can call
            │
            ▼
4. LLM agent (ReAct loop)            reasons step by step, proposes an attack path
```

Running alongside for scoring: a set of Cypher queries that compute the true shortest paths
(the answer key), and a logger that records every agent run.

### 4.1 The agent's tools

The agent is **not** handed the whole graph as text — that would reduce the test to text
pattern-matching. Instead it gets a few query tools and must explore, exactly like a human
clicking through BloodHound:

| Tool | What it returns |
| --- | --- |
| `query_outbound_edges(node)` | What this object can control / reach (full-control rights, member-of, reset-password, etc.) |
| `query_inbound_edges(node)` | What can control / reach this object |
| `search_node(name_or_type)` | Find a user, group, or computer by name or type |
| `check_path_exists(start, end)` | Verify whether a proposed chain actually exists in the graph (agent self-check + your scoring) |

### 4.2 How one run works, end to end

1. You pick a starting node ('user A has just been phished') and a goal ('any Domain Admin').
2. The agent calls tools to explore outward from user A, observing what each account can do.
3. It reasons about which relationships chain together toward the goal.
4. It outputs a proposed attack path (an ordered list of hops) with a short justification for each hop.
5. Your scoring script runs `check_path_exists` / Cypher to confirm whether that path is real,
   records the time taken, number of tool calls, and whether it matches (or beats) BloodHound's own answer.

---

## Part 5 — Technology Stack

### 5.1 Data + database (the part that used to need Windows)

| Component | Tool / Technology |
| --- | --- |
| Graph database | Neo4j Community Edition, run as a single Docker container |
| Synthetic data generator | DBCreator (michiellemmens fork recommended) — Python 3.7+, `neo4j` driver |
| Ground-truth queries | Cypher (Neo4j's query language) — shortest-path queries as the answer key |
| Optional visualiser | Legacy BloodHound GUI, only if you want to see the graph; not required to run the study |

### 5.2 Agent / AI layer

| Component | Tool / Technology |
| --- | --- |
| Language | Python 3 |
| Agent loop | Minimal custom ReAct loop (reason → call tool → observe → repeat). Keep it lightweight |
| LLM access | Anthropic API (Claude) and/or OpenAI API — one model is enough to start, two enables comparison |
| Tool calling | Native function-calling / tool-use API |
| Graph query bridge | Python + official `neo4j` driver, wrapping Cypher as the 4 callable tools |

### 5.3 Evaluation + write-up

| Component | Tool / Technology |
| --- | --- |
| Scoring | Cypher checks for path validity; Python to compare against BloodHound's answer |
| Logging | One structured CSV/JSON record per run (model, scenario, tool calls, path, time, correct?) |
| Analysis / plots | pandas + matplotlib |
| Paper | LaTeX (IEEE template) or Markdown, depending on target venue |

---

## Part 6 — Revised Build Plan (Laptop-Friendly)

Because the Windows lab is gone, the old 'stand up a forest' week collapses into a few
hours. The plan below fits a solo ~2.5–3 week sprint; if you only have two weeks, compress
Week 1 and use a single model.

### Week 1 — Data + Baseline (now the easy part)

- **Day 1:** Run Neo4j in Docker. Clone the DBCreator fork, install the `neo4j` driver, connect it to your Neo4j instance.
- **Day 2:** Generate a synthetic graph (start small, e.g. 300–500 nodes). Confirm data loaded. Optionally plant 2–3 specific misconfiguration chains via Cypher.
- **Day 3:** Write Cypher shortest-path queries to extract the ground-truth attack paths — this is your answer key and your BloodHound-equivalent baseline. Record the paths and how long the queries take.

### Week 2 — Build the Agent

- **Days 4–5:** Implement the 4 graph-query tools as Python functions wrapping Cypher. Test each in isolation.
- **Days 6–7:** Build the ReAct loop, connect one LLM, and get it to solve the simplest known path first. Debug the prompt and tool-calling until it reliably reaches the goal node.
- **Day 8:** Add automated logging so every run captures tool calls, final path, time, and correctness.

### Week 3 — Benchmark + Write-Up

- **Days 9–10:** Run repeated trials across several graph sizes (regenerate with more nodes for a scaling curve). If time allows, add a second model.
- **Days 11–12:** Score everything — path-correctness rate, hallucination rate, time, tool-call count — and make the comparison-vs-BloodHound table and plots.
- **Days 13–15:** Draft the short paper (problem, method, results, limitations, ethics) and package the code + logs as a reproducible artifact.

---

## Part 7 — Metrics (Your Results Table)

| Metric | Meaning |
| --- | --- |
| Path-correctness rate | % of runs where the proposed path is verified as real in the graph |
| Hallucination rate | % of runs proposing an edge or hop that does not exist |
| Time-to-solution | Wall-clock time to the final answer |
| Tool-call efficiency | Number of queries used to reach a correct answer |
| Scaling behaviour | How correctness and time change as the graph grows (300 → 2,000+ nodes) |
| Gap vs. BloodHound | Cases where the agent finds paths BloodHound's queries miss, or vice versa |

---

## Part 8 — Handling the 'Synthetic Data' Question in Your Paper

A reviewer will ask why you didn't test on real data. Address it head-on and it becomes a
non-issue:

- State plainly that you evaluated on synthetic AD graphs conforming to the BloodHound schema — the same structure real collections use — which lets you control graph size and guarantee ground truth.
- Note that synthetic evaluation is standard practice for reproducible benchmarks, since it removes organisation-specific noise and privacy concerns.
- List 'validation on live-collected AD data' explicitly as future work. Reviewers accept this readily for a proof-of-concept or short paper.

---

## Part 9 — Hardware & Safety Notes

### 9.1 What your machine actually needs now

- A Docker-capable laptop with a few GB of free RAM — Neo4j + a Python script is light. Your HP Victus is far more than enough.
- No Windows VMs, no domain controller, no GOAD, no large virtual network.
- The only external cost is a small amount of LLM API credit, which scales with (models × scenarios × trials × tool calls) — cap trial counts to keep it cheap.

### 9.2 Ethics

- Because the data is fully synthetic and local, there is no live network involved — which also makes the ethics story clean.
- If you later add a real single-DC collection step for authenticity, only ever run collection tooling against an environment you own or are explicitly authorised to test.
- State in the write-up that all experiments used synthetic, locally-generated data.

---

> *Revised plan for the synthetic-data (Option 1) approach. Verify the current state of the
> DBCreator fork before Day 1, and keep a small hand-written Cypher graph-insert script as a
> fallback in case the generator needs patching for your Neo4j version.*

---

## Appendix — How this repo deviates from the original plan

The plan above is the **source brief**. A few decisions changed during the build, for good
reasons — recorded here so the plan and the code don't appear to contradict each other:

- **Database:** Neo4j **Aura Free (cloud)** instead of Neo4j Community in Docker — this
  machine has no Docker. Same Cypher, same driver, same schema.
- **Generator:** a **custom seeded generator** (`data/generator/generate.py`, `seed=1337`)
  instead of DBCreator — the DBCreator fork breaks on Neo4j 5.x / Aura. This is exactly the
  "hand-written Cypher graph-insert fallback" the plan's closing note recommends. Bonus: a
  fixed seed makes the graph fully reproducible.
- **LLM:** currently **Gemini** (`gemini-3.1-flash-lite`) rather than Anthropic/OpenAI. A
  second model for comparison is still open.
