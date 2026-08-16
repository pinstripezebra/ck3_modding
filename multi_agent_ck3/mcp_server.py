"""Thin FastMCP facade — exposes the LangGraph supervisor as a single MCP tool.

VS Code connects to this server.  All context-window pressure from the 15
individual tool definitions is hidden behind the supervisor; Copilot only
sees one tool: `ck3_mod_task`.
"""
import pathlib
import sys

# Ensure multi_agent_ck3/ is on the path when launched as a module
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("ck3-multi-agent")

# Lazy-load the supervisor so the server starts instantly and only pays the
# model-initialisation cost on the first tool call.
_supervisor = None


def _get_supervisor():
    global _supervisor
    if _supervisor is None:
        from graph import build_graph
        _supervisor = build_graph()
    return _supervisor


@mcp.tool()
def ck3_mod_task(task: str) -> str:
    """Execute any CK3 modding task via the multi-agent supervisor.

    The supervisor automatically routes your request to the correct specialist:
    - Traits, perks, buildings, artifacts, decisions  → content agent
    - Religions, cultures                              → world agent
    - Character interactions, events                  → events agent
    - GUI files, DDS icons                             → GUI agent
    - File inspection, docs, validation, mod scaffold,
      error log analysis                               → core agent

    Args:
        task: Natural-language description of what you want to create or do.
              Include all relevant details (mod name, IDs, modifiers, etc.).
    Returns:
        A summary of everything that was created or found, including file paths.
    """
    supervisor = _get_supervisor()
    result = supervisor.invoke({"messages": [HumanMessage(content=task)]})
    return result["messages"][-1].content


if __name__ == "__main__":
    mcp.run()
