"""Core agent — file inspection, docs retrieval, validation, mod management, error logs."""
import os
import sys

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
Use read_mod_file (not check_ck3_file) to inspect a file that already exists in one of
our OWN mods (e.g. ElderMagic) rather than a vanilla game file.
Use edit_mod_file to make a targeted change to an EXISTING mod file (e.g. adding a
field to an existing trait/building/etc.) — the create_* tools on other agents only
generate brand-new content and cannot modify something that already exists.
MANDATORY before any edit_mod_file call: call read_mod_file on that exact file FIRST
in the same turn-sequence to see its real current content — never guess old_text from
memory or a prior summary. Use the SHORTEST line that uniquely identifies the target
block (e.g. its own icon/filename reference) as old_text, not a multi-line snippet —
multi-line text is fragile against whitespace/newline differences and wastes repeated
failed attempts. When the same field needs adding to several near-identical blocks,
make one edit_mod_file call per block using that block's own unique anchor, and do not
repeat a call once it has already reported success for that block.
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
        ck3_file_checker.get_tools(CK3_GAME_DIR, repo_root=REPO_ROOT)
        + cross_reference.get_tools(REPO_ROOT, CK3_GAME_DIR)
        + mod_management.get_tools(OUTPUT_DIR, mods_dir=REPO_ROOT)
        + error_logs.get_tools()
        + knowledge_map.get_tools(REPO_ROOT)
    )
    try:
        # Doc/validation tools need a vectorstore, which needs OpenAI embeddings
        # (Anthropic has no embeddings API) — skip immediately (no construction
        # attempt at all) rather than blocking graph build on a hung/slow client
        # when the credential isn't even present.
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not set")
        # get_vectorstore() (OpenAIEmbeddings/Chroma construction) has hung for
        # minutes in practice despite disabling chromadb telemetry -- bound it
        # with a hard timeout so a hang here degrades to "skip docs/validation
        # tools" instead of blocking the entire supervisor's construction.
        # A daemon thread (not ThreadPoolExecutor) so a timeout leaks at most a
        # cheap background thread instead of a pool that lingers for the rest
        # of this long-lived server process's life across repeated retries.
        import threading
        result: dict = {}
        t = threading.Thread(target=lambda: result.update(vs=get_vectorstore()), daemon=True)
        t.start()
        t.join(timeout=15.0)
        if t.is_alive() or "vs" not in result:
            raise RuntimeError("get_vectorstore() timed out after 15.0s")
        vs = result["vs"]
        tool_list += docs.get_tools(vs) + validation.get_tools(vs)
    except Exception as exc:
        print(f"[core_agent] skipping doc/validation tools: {exc!r}", file=sys.stderr, flush=True)
    return create_react_agent(llm, tool_list, prompt=_SYSTEM)
