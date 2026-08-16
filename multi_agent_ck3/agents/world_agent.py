"""World agent — religions and cultures."""
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from shared.paths import REPO_ROOT
from tools import religions, cultures

_SYSTEM = """You are a CK3 world-building specialist.
You create new religions (with faiths, doctrines, holy sites) and cultures
(with traditions, ethos, heritage).
Always check the vanilla CK3 format before generating any new file."""


def get_agent(llm: ChatOpenAI):
    tool_list = (
        religions.get_tools(REPO_ROOT)
        + cultures.get_tools(REPO_ROOT)
    )
    return create_react_agent(llm, tool_list, state_modifier=_SYSTEM)
