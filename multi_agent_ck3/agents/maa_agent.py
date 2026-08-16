"""Men-at-arms agent — creates and manages MaA unit type definitions."""
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from shared.paths import REPO_ROOT, CK3_GAME_DIR
from tools import men_at_arms, ck3_file_checker, validation

_SYSTEM = """You are a CK3 military units specialist.
You create men-at-arms unit type definitions (common/men_at_arms_types/).

Rules:
- Always call check_ck3_file with file_type='men_at_arms' first to inspect the
  vanilla format before generating any new unit.
- Valid unit types: heavy_infantry, light_cavalry, heavy_cavalry, archers,
  skirmishers, pikemen, siege_weapons, special.
- Valid terrain bonus keys: plains, farmlands, hills, mountains, forest, taiga,
  drylands, desert, floodplains, oasis, wetlands, steppe, jungle, arctic.
- siege_tier and siege_value are optional — only add them for units with siege roles.
- can_recruit_trigger gates which cultures/characters can recruit the unit;
  use 'culture = { has_innovation = X }' for innovation-gated units.
- Call validate_script on the generated file before reporting success.
- Write to WizardMod unless the user specifies a different mod_name."""


def get_agent(llm: ChatOpenAI):
    tool_list = (
        men_at_arms.get_tools(REPO_ROOT)
        + ck3_file_checker.get_tools(CK3_GAME_DIR)
        + validation.get_tools(vectorstore=None)  # brace/encoding checks; no vectorstore needed
    )
    return create_react_agent(llm, tool_list, state_modifier=_SYSTEM)
