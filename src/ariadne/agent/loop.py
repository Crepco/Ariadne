import json

from .llm import ask_llm
from .prompts import SYSTEM_PROMPT
from .tool_registry import TOOLS


MAX_STEPS = 10


def run_agent(start_node: str):
    """
    Minimal ReAct loop.

    Reason
      ↓
    Call Tool
      ↓
    Observe
      ↓
    Repeat
    """

    history = []

    history.append(
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    )

    history.append(
        {
            "role": "user",
            "content": f"""
Starting node: {start_node}

Available tools:

- search_node
- query_outbound_edges
- query_inbound_edges
- check_path_exists

Respond ONLY in JSON.

Example:

{{
  "action":"search_node",
  "input":"USER0001"
}}

or

{{
  "action":"finish",
  "answer":"..."
}}
""",
        }
    )

    for step in range(MAX_STEPS):

        print(f"\n========== STEP {step+1} ==========")

        prompt = "\n".join(msg["content"] for msg in history)

        response = ask_llm(prompt)

        print("LLM:")
        print(response)

        try:
            action = json.loads(response)

        except Exception:
            return response

        if action["action"] == "finish":
            return action["answer"]

        tool = action["action"]

        argument = action["input"]

        if tool not in TOOLS:
            return f"Unknown tool: {tool}"

        print(f"\nCalling {tool}({argument})")

        observation = TOOLS[tool](argument)

        print(observation)

        history.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        history.append(
            {
                "role": "user",
                "content": f"Observation:\n{observation}",
            }
        )

    return "Maximum reasoning steps exceeded."