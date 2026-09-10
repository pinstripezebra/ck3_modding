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


@mcp.tool()
def ck3_check_references(mod_name: str, other_mods: list | None = None) -> str:
    """Check a mod's cross-mod references for crash-causing errors. Deterministic.

    Runs directly, without the LLM supervisor, so it is fast and gives the same
    answer every time. Use this FIRST when diagnosing a crash — most CK3 hard
    crashes are an unresolved or colliding reference against another mod, which
    per-file validators cannot see.

    Checks interaction category index uniqueness/contiguity, undefined category
    references, men-at-arms modifiers targeting a unit key instead of an
    archetype, and undefined trait references.

    Args:
        mod_name: Mod folder name inside the repo root (e.g. 'ElderMagic').
        other_mods: Absolute paths to other mod folders in the load order.
    Returns:
        A grouped report of issues, or 'No reference issues found.'
    """
    from shared.paths import REPO_ROOT, CK3_GAME_DIR
    from tools import cross_reference

    mod_root = REPO_ROOT / mod_name
    if not mod_root.is_dir():
        return f"Mod folder not found: {mod_root}"

    others = [pathlib.Path(p) for p in (other_mods or [])]
    results = cross_reference.audit(
        mod_root, CK3_GAME_DIR, [p for p in others if p.is_dir()]
    )
    lines = []
    for group, issues in results.items():
        if issues:
            lines.append(f"[{group}]")
            lines.extend(f"  - {i}" for i in issues)
    return "\n".join(lines) if lines else "No reference issues found."


if __name__ == "__main__":
    mcp.run()
