from .llm import ask_llm
from .prompts import SYSTEM_PROMPT
from .tool_registry import TOOLS




def run_agent(start):
    print("Searching node...")

    user = TOOLS["search_node"](start)

    if not user:
        return f"User '{start}' not found."

    print(user)

    print("\nChecking outbound edges...")

    edges = TOOLS["query_outbound_edges"](user[0]["objectid"])

    print(edges)

    prompt = f"""
You are a cybersecurity analyst.

Given the following Active Directory graph information, explain what privileges
the user has and what attack opportunities might exist.

User:
{user}

Outbound edges:
{edges}

Respond in plain English.
"""

    return ask_llm(prompt)