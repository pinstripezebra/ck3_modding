"""GUI agent — interface files and trait/building icons."""
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from shared.paths import REPO_ROOT, OUTPUT_DIR
from tools import gui_tooling, icons

_SYSTEM = """You are a CK3 GUI and icon specialist.
You create .gui layout files, generate DDS trait/perk/building icons via Flux,
and lint UI files for layout errors.
Always call lint_gui_layout after writing a .gui file and fix every warning before finishing."""


def get_agent(llm: ChatOpenAI):
    tool_list = (
        gui_tooling.get_tools(REPO_ROOT)
        + icons.get_tools(OUTPUT_DIR, mods_dir=REPO_ROOT)
    )
    return create_react_agent(llm, tool_list, state_modifier=_SYSTEM)
