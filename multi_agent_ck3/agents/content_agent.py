"""Content agent — traits, perks, buildings, artifacts, decisions."""
import pathlib
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from shared.paths import REPO_ROOT, OUTPUT_DIR
from tools import traits, perks, buildings, artifacts, decisions

_SYSTEM = """You are a CK3 mod content specialist.
You create traits, lifestyle perks, duchy buildings, artifacts, and decisions.
Always call check_ck3_file first to inspect the vanilla format before generating any new content.
Write files to the WizardMod folder unless the user specifies a different mod_name."""


def get_agent(llm: ChatOpenAI):
    tool_list = (
        traits.get_tools(REPO_ROOT)
        + perks.get_tools(REPO_ROOT)
        + buildings.get_tools(REPO_ROOT)
        + artifacts.get_tools(OUTPUT_DIR)
        + decisions.get_tools(REPO_ROOT)
    )
    return create_react_agent(llm, tool_list, state_modifier=_SYSTEM)
