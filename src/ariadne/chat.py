"""Grounded chat assistant over a BloodHound / Ariadne graph.

A CLI/REPL front-end to the verified reader. You ask in English; an LLM *router*
maps the question to a grounded operation — a vulnerability check, a verified
escalation-path search, triage, a path explanation, or a read-only Cypher query —
and the answer comes from the graph, not the model's imagination.

**Safety invariant:** the assistant never asserts a path or finding the graph does
not confirm. Checks are deterministic; a proposed escalation path is run through
the verifier (``evaluation/score.py``) and only shown if it holds up; free-form
questions become *read-only* Cypher (writes are refused). The LLM only routes and
summarises grounded results.

Run it::

    python -m ariadne.chat          # or the `ariadne-chat` console script
"""

from __future__ import annotations

import json
import re

from ariadne.agent.llm import chat
from ariadne.checks import CHECKS, run_check
from ariadne.db import run_read
from ariadne.report import explain_path, rank_paths

# Write clauses, as whole words. Matching on whitespace-delimited words rather
# than substrings avoids both directions of error the old list had: `"SET "`
# (with a literal trailing space) missed `SET\n`, while a bare `"CREATE"` would
# flag a node named `CREATED_BY`.
#
# This is a *pre-filter*, not the security boundary — it exists to give a clear
# refusal message. The actual guarantee is that `db.run_read` runs inside an
# explicit READ transaction, so Neo4j itself rejects a write whatever slips past
# this regex.
_WRITE_CLAUSES = (
    "CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP",
    "FOREACH", "LOAD",
)
_WRITE_RE = re.compile(r"\b(" + "|".join(_WRITE_CLAUSES) + r")\b", re.IGNORECASE)
# A CALL subquery can hide writes; a plain `CALL db.labels()` is a legitimate
# read, so only the subquery form is flagged.
_SUBQUERY_RE = re.compile(r"\bCALL\s*\{", re.IGNORECASE)

_ROUTER_SYSTEM = """You route a security analyst's question about an Active Directory
graph to ONE grounded operation. Reply with a single JSON object, nothing else:

{ "intent": "<intent>", "args": { ... } }

Intents:
  list_checks                      - list the available vulnerability checks
  check    {"name": "<check>"}     - run a named vulnerability check
  find_path{"start": "<node>"}     - find a verified escalation path from a node to Domain Admins
  triage                           - rank the most impactful findings
  explain  {"ref": "last"|"1"}     - explain a previously found path/finding
  cypher   {"query": "<read-only Cypher>"}  - answer a specific graph question
  help                             - explain what you can do

Available checks: {checks}

Never invent findings or paths; if unsure, use intent "help". Output ONLY the JSON."""


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without a database or network)
# ---------------------------------------------------------------------------
def is_read_only(query: str) -> bool:
    """True if a Cypher query contains no write clause.

    A fast pre-filter for a friendly refusal message. ``db.run_read`` enforces
    read-only access server-side regardless, so a false negative here is a worse
    error message, not a write.
    """
    text = query or ""
    return not (_WRITE_RE.search(text) or _SUBQUERY_RE.search(text))


def parse_intent(text: str) -> dict:
    """Parse the router's JSON reply into ``{intent, args}``; default to help."""
    try:
        start, end = text.find("{"), text.rfind("}")
        obj = json.loads(text[start : end + 1]) if start != -1 and end > start else {}
    except Exception:
        obj = {}
    if not isinstance(obj, dict) or "intent" not in obj:
        return {"intent": "help", "args": {}}
    args = obj.get("args")
    return {"intent": obj["intent"], "args": args if isinstance(args, dict) else {}}


def route(question: str) -> dict:
    """Ask the LLM router to classify a question into a grounded intent."""
    system = _ROUTER_SYSTEM.replace("{checks}", ", ".join(CHECKS))
    reply = chat([
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]).text
    return parse_intent(reply)


# ---------------------------------------------------------------------------
# Grounded executors
# ---------------------------------------------------------------------------
def _fmt_findings(findings) -> str:
    if not findings:
        return "No findings."
    return "\n".join(f"  [{f.severity}] {f.subject}: {f.detail}" for f in findings)


def do_check(ctx, args, state) -> str:
    name = args.get("name")
    if name not in CHECKS:
        return f"Unknown check {name!r}. Available: {', '.join(CHECKS)}"
    findings = run_check(name, ctx)
    state["last_findings"] = findings
    return f"{name} — {len(findings)} finding(s):\n{_fmt_findings(findings)}"


def do_find_path(ctx, args, state) -> str:
    from ariadne.agent.loop import run_agent
    from ariadne.evaluation.score import parse_path_tokens, verify_path

    start = args.get("start")
    if not start:
        return "Which node should I start from?"
    result = run_agent(start, verbose=False)
    tokens = parse_path_tokens(getattr(result, "answer", ""), getattr(result, "path_field", None))
    v = verify_path(ctx, tokens)
    if not v["valid"]:
        return (f"No VERIFIED path to Domain Admins found from {start} "
                f"(the model's proposal did not check out against the graph).")
    state["last_path"] = [h["from"] for h in v["hop_edges"]] + [v["hop_edges"][-1]["to"]]
    names = " -> ".join(ctx.names.get(o, o) for o in state["last_path"])
    inferred = sum(1 for h in v["hop_edges"] if h["inferred"])
    tag = f" ({inferred} inferred step(s) BloodHound's canonical query can't see)" if inferred else ""
    return f"Verified path from {start}:\n  {names}{tag}"


def do_triage(ctx, args, state) -> str:
    findings = state.get("last_findings")
    if not findings:
        return "Run a check first (e.g. 'find kerberoastable paths'), then I can triage."
    # Rank the single-node findings by property impact.
    paths = [[ctx.name_to_oid.get(f.subject.upper(), f.subject)] for f in findings]
    ranked = rank_paths(ctx, paths)
    return "Top findings by impact:\n" + "\n".join(
        f"  {i+1}. {r['path'][0]} — {r['reason']}" for i, r in enumerate(ranked[:10])
    )


def do_explain(ctx, args, state) -> str:
    path = state.get("last_path")
    if not path:
        return "I don't have a path to explain yet — try 'find a path from <node>' first."
    return explain_path(ctx, path)


def do_cypher(ctx, args, state) -> str:
    query = args.get("query", "")
    if not query:
        return "No query given."
    if not is_read_only(query):
        return "Refused: that Cypher contains a write clause. This assistant is read-only."
    try:
        rows = run_read(ctx.driver, query, database=ctx.database)
    except Exception as e:  # noqa: BLE001
        return f"Query error: {e}"
    if not rows:
        return "No results."
    return "\n".join(str(r) for r in rows[:25])


def do_help(ctx, args, state) -> str:
    lines = ["I answer from the graph (never guessing). I can:",
             "  - run vulnerability checks: " + ", ".join(CHECKS),
             "  - find a VERIFIED escalation path: 'find a path from USER0007'",
             "  - triage findings, explain a path, or answer a read-only Cypher question."]
    return "\n".join(lines)


_DISPATCH = {
    "list_checks": lambda ctx, a, s: "Checks: " + "; ".join(f"{n} — {d}" for n, (_f, d) in CHECKS.items()),
    "check": do_check,
    "find_path": do_find_path,
    "triage": do_triage,
    "explain": do_explain,
    "cypher": do_cypher,
    "help": do_help,
}


def handle(question: str, ctx, state: dict) -> str:
    """Route a question and execute the grounded operation. Core of the REPL."""
    intent = route(question)
    fn = _DISPATCH.get(intent["intent"], do_help)
    return fn(ctx, intent.get("args", {}), state)


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------
def main() -> None:
    from ariadne.evaluation.score import ScoringContext

    print("Ariadne — grounded AD security assistant. Ask a question, or 'quit'.")
    ctx = ScoringContext.load()
    state: dict = {}
    try:
        while True:
            try:
                question = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not question:
                continue
            if question.lower() in ("quit", "exit", "q"):
                break
            try:
                print(handle(question, ctx, state))
            except Exception as e:  # noqa: BLE001 — keep the REPL alive
                print(f"(error: {e})")
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
