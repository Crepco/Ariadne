"""The tool name -> callable map the agent loop dispatches on.

Single source of truth is ``ariadne.tools.TOOLS``; this module just re-exports it
so ``from .tool_registry import TOOLS`` keeps working for the loop.
"""

from ariadne.tools import TOOLS

__all__ = ["TOOLS"]
