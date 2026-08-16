"""Events agent — character interactions and game events."""
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from shared.paths import REPO_ROOT
from tools import interactions_events

_SYSTEM = """You are a CK3 narrative and events specialist.
You create character interactions and scripted events.
Keep effect/trigger blocks syntactically valid CK3 script.
Validate every generated script with validate_script before reporting success."""


def get_agent(llm: ChatOpenAI):
    tool_list = interactions_events.get_tools(REPO_ROOT)
    return create_react_agent(llm, tool_list, state_modifier=_SYSTEM)
