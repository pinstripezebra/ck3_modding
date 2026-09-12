"""Core agent — file inspection, docs retrieval, validation, mod management, error logs."""
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from shared.paths import REPO_ROOT, OUTPUT_DIR, CK3_GAME_DIR, get_vectorstore
from tools import (
    ck3_file_checker,
    cross_reference,
    docs,
    validation,
    mod_management,
    error_logs,
    knowledge_map,
)

_SYSTEM = """You are a CK3 modding infrastructure specialist.
You inspect vanilla game files, retrieve modding documentation, validate scripts,
scaffold/package mods, diagnose CK3 error logs, and generate knowledge maps.
Use check_ck3_file to confirm exact vanilla syntax before other agents generate content.
Call generate_knowledge_map after any content creation run to keep the mod map up to date.

When diagnosing a crash or bug, work in this order:
1. validate_mod_references FIRST — most crashes are an unresolved or colliding
   cross-mod reference, and validate_script cannot see those.
2. check_ck3_file on the vanilla file being overridden, and READ ITS COMMENTS —
   Paradox documents hard constraints there (e.g. interaction category indices
   must be unique and contiguous or the game crashes).
3. parse_error_log — note that a hard crash often writes NOTHING to error.log,
   so an empty result does not exonerate anything.
4. Treat the last line of game.log as the *previous* user action, not the crash
   site. CK3 logs window opens but not menu opens."""


def get_agent(llm: ChatOpenAI):
    tool_list = (
        ck3_file_checker.get_tools(CK3_GAME_DIR)
        + cross_reference.get_tools(REPO_ROOT, CK3_GAME_DIR)
        + mod_management.get_tools(OUTPUT_DIR, mods_dir=REPO_ROOT)
        + error_logs.get_tools()
        + knowledge_map.get_tools(REPO_ROOT)
    )
    try:
        # Doc/validation tools need a vectorstore, which needs OpenAI embeddings
        # (Anthropic has no embeddings API) — skip them rather than blocking the
        # whole supervisor when OPENAI_API_KEY isn't set.
        vs = get_vectorstore()
        tool_list += docs.get_tools(vs) + validation.get_tools(vs)
    except Exception:
        pass
    return create_react_agent(llm, tool_list, prompt=_SYSTEM)
