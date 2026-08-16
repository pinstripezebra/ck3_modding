"""Core agent — file inspection, docs retrieval, validation, mod management, error logs."""
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from shared.paths import REPO_ROOT, OUTPUT_DIR, CK3_GAME_DIR, get_vectorstore
from tools import ck3_file_checker, docs, validation, mod_management, error_logs, knowledge_map

_SYSTEM = """You are a CK3 modding infrastructure specialist.
You inspect vanilla game files, retrieve modding documentation, validate scripts,
scaffold/package mods, diagnose CK3 error logs, and generate knowledge maps.
Use check_ck3_file to confirm exact vanilla syntax before other agents generate content.
Call generate_knowledge_map after any content creation run to keep the mod map up to date."""


def get_agent(llm: ChatOpenAI):
    vs = get_vectorstore()
    tool_list = (
        ck3_file_checker.get_tools(CK3_GAME_DIR)
        + docs.get_tools(vs)
        + validation.get_tools(vs)
        + mod_management.get_tools(OUTPUT_DIR, mods_dir=REPO_ROOT)
        + error_logs.get_tools()
        + knowledge_map.get_tools(REPO_ROOT)
    )
    return create_react_agent(llm, tool_list, state_modifier=_SYSTEM)
