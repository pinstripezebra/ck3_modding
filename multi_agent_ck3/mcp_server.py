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

# Explicit path: the server's cwd is multi_agent_ck3/, and load_dotenv()'s
# default upward search does not reliably run from a VS-Code-spawned process.
load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")

mcp = FastMCP("ck3-multi-agent")

# Lazy-load the supervisor so the server starts instantly and only pays the
# model-initialisation cost on the first tool call.
_supervisor = None


def _run_with_timeout(fn, timeout: float, label: str):
    """Run fn() in a daemon thread so a hang raises instead of blocking forever.

    Uses a raw daemon threading.Thread instead of ThreadPoolExecutor: a pool's
    worker thread is NOT a daemon thread, so every timed-out call used to leak
    a thread that lingers for the rest of the server process's life -- over
    many retries in one long-lived process this accumulated into dozens of
    threads contending for the GIL, which was itself slowing down later calls.
    A daemon thread leaks far more cheaply (it never blocks process exit and
    is scheduled like any other background thread, not specially retained by
    a pool object), and we only ever need one result from one call here.
    """
    import threading

    result: dict = {}

    def _runner():
        try:
            result["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - surface any failure to the waiter
            result["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    if thread.is_alive():
        print(f"[mcp_server] {label} TIMED OUT after {timeout}s", file=sys.stderr, flush=True)
        raise RuntimeError(f"{label} timed out after {timeout}s") from None
    if "error" in result:
        raise result["error"]
    return result["value"]


def _get_supervisor():
    global _supervisor
    if _supervisor is None:
        print("[mcp_server] building supervisor graph...", file=sys.stderr, flush=True)

        def _import_and_build():
            # `graph` module-level code eagerly builds `supervisor_graph` for
            # langgraph.json/LangGraph Studio compatibility -- that build runs as
            # a side effect of THIS import statement, unprotected by any timeout,
            # the very first time the module loads. Importing inside the worker
            # thread (instead of a bare top-level `from graph import build_graph`
            # in this function) puts that implicit build under the SAME timeout
            # below, and reuses it instead of constructing a second, redundant
            # supervisor via our own separate build_graph() call.
            from graph import supervisor_graph
            return supervisor_graph

        # Construction should be near-instant (no LLM calls) -- a low cap catches
        # a hung dependency (e.g. a vectorstore/embeddings client) fast and loud
        # instead of silently blocking for many minutes with no trace/timeout.
        _supervisor = _run_with_timeout(_import_and_build, timeout=60.0, label="build_graph")
        print("[mcp_server] supervisor graph built", file=sys.stderr, flush=True)
    return _supervisor


def _invoke_with_timeout(supervisor, task: str, timeout: float = 600.0) -> str:
    def _run():
        print("[mcp_server] invoke starting...", file=sys.stderr, flush=True)
        result = supervisor.invoke(
            {"messages": [HumanMessage(content=task)]},
            config={
                "run_name": "ck3_supervisor",
                "tags": ["supervisor"],
                "metadata": {"task": task},
                # 15 was too aggressive once real multi-step edits (check vanilla
                # format, read_mod_file, several edit_mod_file calls) are legitimate
                # work, not thrashing -- confirmed by a real GraphRecursionError on
                # a correctly-scoped task. 40 still fails fast on genuine loops
                # while giving normal multi-tool-call tasks enough headroom.
                "recursion_limit": 40,
            },
        )
        print("[mcp_server] invoke finished", file=sys.stderr, flush=True)
        return result["messages"][-1].content

    return _run_with_timeout(_run, timeout=timeout, label="invoke")


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
    return _invoke_with_timeout(supervisor, task)


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
