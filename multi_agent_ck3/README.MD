# CK3 Multi-Agent Modding System

A LangGraph-based multi-agent system that replaces the single monolithic MCP server in `ck3_agent/`. Instead of loading all 15 tool modules into every prompt, a supervisor LLM routes each task to the correct specialist sub-agent — each of which only loads the tools it needs.

---

## Why This Exists

The original `ck3_agent/src/main.py` registered all tools into one FastMCP server. Every Copilot prompt received the full tool schema for all 15 modules, consuming significant context window even for simple tasks. This architecture fixes that by limiting each agent's context to its domain.

---

## Architecture

```
VS Code Copilot
      │
      │  one MCP tool: ck3_mod_task(task)
      ▼
mcp_server.py  (FastMCP facade)
      │
      ▼
graph.py  —  Supervisor ReAct agent (GPT-4o)
      │
      │  routes via tool calls to:
      ├──► content_agent   traits · perks · buildings · artifacts · decisions
      ├──► world_agent     religions · cultures
      ├──► events_agent    character interactions · scripted events
      ├──► gui_agent       GUI files · DDS icons (via Flux)
      └──► core_agent      vanilla file inspection · docs retrieval ·
                           script validation · mod scaffold/package ·
                           error log analysis
```

Each sub-agent is a `create_react_agent` with only the tools relevant to its domain. The supervisor is also a `create_react_agent` whose tools are the five sub-agents (each wrapped as a `StructuredTool`).

---

## Project Structure

```
multi_agent_ck3/
├── mcp_server.py           FastMCP server — the single VS Code entry point
├── graph.py                Supervisor graph; also the langgraph.json entry point
├── langgraph.json          LangGraph Studio / CLI configuration
├── requirements.txt
│
├── shared/
│   └── paths.py            Common path constants and lazy vectorstore factory
│
├── agents/
│   ├── content_agent.py    traits, perks, buildings, artifacts, decisions
│   ├── world_agent.py      religions, cultures
│   ├── events_agent.py     character interactions, events
│   ├── gui_agent.py        GUI files, DDS icons
│   └── core_agent.py       file checker, docs, validation, mod management, error logs
│
└── tools/                  Ported from ck3_agent/src/tools/ — each file gains
    │                       a get_tools() factory alongside its register() function
    ├── traits.py
    ├── perks.py
    ├── buildings.py
    ├── artifacts.py
    ├── decisions.py
    ├── religions.py
    ├── cultures.py
    ├── interactions_events.py
    ├── gui_tooling.py
    ├── icons.py
    ├── ck3_file_checker.py
    ├── docs.py
    ├── validation.py
    ├── mod_management.py
    ├── error_logs.py
    └── gui_quality.py      (shared quality/lint helpers for gui_tooling)
```

---

## Tool Module Pattern

Every tool module exposes two public interfaces:

```python
# Original MCP registration — kept for backward compatibility
def register(mcp, output_dir): ...

# New: return LangChain StructuredTool objects for use inside agents
def get_tools(output_dir) -> list: ...
```

`get_tools()` works by passing a lightweight `_ToolCollector` stub (which mimics `FastMCP`'s `.tool()` decorator) into the existing `register()` function and converting the collected closures into `StructuredTool` objects. No tool logic was duplicated.

---

## Agent → Tool Mapping

| Agent | Tools |
|---|---|
| `content_agent` | `create_trait`, `create_perk`, `create_building`, `generate_artifact`, `create_decision` |
| `world_agent` | `create_religion`, `create_culture` |
| `events_agent` | `create_interaction`, `create_event` |
| `gui_agent` | `lint_gui_layout`, `lint_mod_gui_layout`, `get_gui_prompt_template`, `generate_trait_icon`, `generate_building_icon`, *(+ other icon tools)* |
| `core_agent` | `check_ck3_file`, `retrieve_docs`, `validate_script`, `scaffold_mod`, `package_mod`, `load_error_log`, `summarise_error_log` |

---

## Setup

### 1. Install dependencies

```bash
# from the ai_dev/ root (the venv is already set up there)
.venv\Scripts\activate
pip install -r multi_agent_ck3\requirements.txt
```

### 2. Configure VS Code MCP

Add to `.vscode/mcp.json` (or your User `settings.json` under `mcp.servers`):

```json
{
  "servers": {
    "ck3-multi-agent": {
      "type": "stdio",
      "command": "C:\\dev\\ai_dev\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server"],
      "cwd": "C:\\dev\\ai_dev\\multi_agent_ck3",
      "env": {}
    }
  }
}
```

### 3. Run with LangGraph Studio

```bash
cd c:\dev\ai_dev\multi_agent_ck3
langgraph dev
```

The `langgraph.json` points to `graph.py:supervisor_graph` so you can visualise and debug the full routing graph in LangGraph Studio.

---

## Extending the System

### Add a new tool to an existing agent

1. Add your function to the relevant module in `tools/` using the same closure pattern.
2. The `_ToolCollector` shim picks it up automatically via `register()` — no extra wiring needed.

### Add a new domain agent

1. Create `agents/my_agent.py` with a `get_agent(llm)` function.
2. In `graph.py`, import it and add it to the `agent_tools` list with a name and description.
3. Update the supervisor's system prompt to describe the new agent's scope.

---

## Shared Data

The `shared/paths.py` module points all path constants at the existing `ck3_agent/` artefacts so there is no data duplication:

| Constant | Points to |
|---|---|
| `REPO_ROOT` | `ai_dev/` |
| `OUTPUT_DIR` | `ai_dev/ck3_agent/output/` |
| `CHROMA_DIR` | `ai_dev/ck3_agent/chroma_db/` |
| `CK3_GAME_DIR` | CK3 Steam installation |

The `WizardMod/` folder at `REPO_ROOT` is the default mod target; pass `mod_name="WizardMod"` (or your mod's name) in any content creation call.
