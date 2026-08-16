"""LangGraph supervisor — routes tasks to the appropriate domain agent.

Architecture
------------
The supervisor is itself a ReAct agent whose "tools" are the seven domain
sub-agents.  Each sub-agent is wrapped as a LangChain StructuredTool so the
supervisor LLM can call it by name with a plain-text task description.

Routing heuristic (the supervisor decides via its system prompt):
  content_agent  → traits, perks, buildings, artifacts, decisions
  world_agent    → religions, cultures
  events_agent   → character interactions, scripted events
  gui_agent      → GUI files, DDS icons, layout linting
  maa_agent      → men-at-arms unit types
  common_agent   → script_values, on_actions, scripted_effects, localization
  core_agent     → file inspection, docs, script validation, mod scaffold,
                   error log analysis
"""
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agents import (
    content_agent, world_agent, events_agent, gui_agent,
    core_agent, maa_agent, common_agent,
)

load_dotenv()

_SUPERVISOR_SYSTEM = """You are the orchestrator for a CK3 mod-building multi-agent system.

You have seven specialist sub-agents available as tools:
- content_agent  : creates traits, perks, buildings, artifacts, decisions
- world_agent    : creates religions and cultures
- events_agent   : creates character interactions and scripted events
- gui_agent      : creates GUI files and generates DDS icons
- maa_agent      : creates men-at-arms unit type definitions
- common_agent   : creates script_values, on_actions, scripted_effects, localization
- core_agent     : inspects vanilla files, retrieves docs, validates scripts,
                   scaffolds/packages mods, reads error logs

MANDATORY WORKFLOW — you MUST follow this order:
1. For ANY content creation task, call core_agent FIRST to check the vanilla
   format of the file type being generated (e.g. check_ck3_file for traits
   before content_agent creates a trait). Include the vanilla format result
   in the task description you pass to the specialist agent.
2. Delegate to the relevant specialist sub-agent(s) in logical order.
3. If the task involves on_actions, script_values, or scripted_effects alongside
   content (e.g. a trait + a supporting XP-grant effect), call common_agent
   AFTER the content agent.
4. If a sub-agent returns an error or parse failure, route to core_agent to
   diagnose via load_error_log or validate_script.
5. Synthesise all sub-agent outputs into a single, clear final response.

ROUTING GUIDE:
- Trait / perk / building / artifact / decision                → content_agent
- Religion / culture                                           → world_agent
- Character interaction / visible event / event chain          → events_agent
- GUI window / DDS icon / GUI lint                             → gui_agent
- Men-at-arms unit type                                        → maa_agent
- script_value / on_action / scripted_effect / localization    → common_agent
- Vanilla file inspection / docs / validation / error logs     → core_agent

KNOWN PITFALLS — pass these facts to specialist agents in your task description:
- .txt script files MUST be UTF-8 without BOM; .yml loc files MUST have UTF-8 BOM.
- Valid trait categories: personality, education, childhood, commander,
  winter_commander, lifestyle, court_type, fame, health. NOT 'physical'.
- XP track thresholds inside a 'track' block must be ≤ 100.
- 'on_trait_gain' and 'on_trait_lost' do NOT exist in CK3.
- 'is_triggered_only = yes' is deprecated for visible character_event types.
- Trait localization keys must be 'trait_X:0' not just 'X:0'.
- 'commander_modifier' is NOT valid inside a trait definition block.

Never attempt to create CK3 files yourself — always delegate to sub-agents."""


def _make_agent_tool(name: str, description: str, agent):
    """Wrap a compiled LangGraph agent as a StructuredTool the supervisor can call."""
    def _run(task: str) -> str:
        result = agent.invoke({"messages": [HumanMessage(content=task)]})
        return result["messages"][-1].content

    return StructuredTool.from_function(
        func=_run,
        name=name,
        description=description,
    )


def build_graph(model: str = "gpt-4o"):
    llm = ChatOpenAI(model=model, temperature=0)

    content = content_agent.get_agent(llm)
    world   = world_agent.get_agent(llm)
    events  = events_agent.get_agent(llm)
    gui     = gui_agent.get_agent(llm)
    core    = core_agent.get_agent(llm)
    maa     = maa_agent.get_agent(llm)
    common  = common_agent.get_agent(llm)

    agent_tools = [
        _make_agent_tool(
            "content_agent",
            "Create CK3 traits, lifestyle perks, duchy buildings, artifacts, or decisions. "
            "Pass the full task description including vanilla format notes from core_agent.",
            content,
        ),
        _make_agent_tool(
            "world_agent",
            "Create CK3 religions (with faiths/doctrines/holy sites) or cultures "
            "(with ethos/traditions/heritage). Pass the full task description.",
            world,
        ),
        _make_agent_tool(
            "events_agent",
            "Create CK3 character interactions or scripted events. "
            "Pass the full task description including trigger/effect blocks.",
            events,
        ),
        _make_agent_tool(
            "gui_agent",
            "Create CK3 .gui files, generate DDS trait/building icons via Flux, "
            "or lint existing GUI files. Pass the full task description.",
            gui,
        ),
        _make_agent_tool(
            "maa_agent",
            "Create CK3 men-at-arms unit type definitions in common/men_at_arms_types/. "
            "Pass unit stats, terrain bonuses, recruit trigger, and mod name.",
            maa,
        ),
        _make_agent_tool(
            "common_agent",
            "Create or append to common/script_values/, common/on_actions/, "
            "common/scripted_effects/, or write localization .yml files. "
            "Pass the full task including variable names, formulas, or effect bodies.",
            common,
        ),
        _make_agent_tool(
            "core_agent",
            "Inspect vanilla CK3 game files, retrieve modding documentation, "
            "validate scripts, scaffold or package a mod, analyse error logs, "
            "or generate/refresh the mod knowledge map. Pass the full task description.",
            core,
        ),
    ]

    return create_react_agent(llm, agent_tools, state_modifier=_SUPERVISOR_SYSTEM)


# Entry point used by langgraph.json
supervisor_graph = build_graph()
