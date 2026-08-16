import pathlib
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from mcp.server.fastmcp import FastMCP

from tools import (
    buildings,
    ck3_file_checker,
    docs,
    icons,
    traits,
    validation,
    mod_management,
    perks,
    religions,
    cultures,
    artifacts,
    decisions,
    interactions_events,
    gui_tooling,
    error_logs,
)

load_dotenv(pathlib.Path(__file__).resolve().parent.parent.parent / ".env", override=True)

CHROMA_DIR = str(pathlib.Path(__file__).resolve().parent.parent / "chroma_db")
OUTPUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "output"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CK3_GAME_DIR = pathlib.Path(r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game")

mcp = FastMCP("ck3-docs")
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

# Register tool groups
ck3_file_checker.register(mcp, CK3_GAME_DIR)
docs.register(mcp, vectorstore)
icons.register(mcp, OUTPUT_DIR, mods_dir=REPO_ROOT)
traits.register(mcp, REPO_ROOT)
validation.register(mcp, vectorstore)
mod_management.register(mcp, OUTPUT_DIR, mods_dir=REPO_ROOT)
perks.register(mcp, REPO_ROOT)
religions.register(mcp, REPO_ROOT)
cultures.register(mcp, REPO_ROOT)
artifacts.register(mcp, REPO_ROOT)
buildings.register(mcp, REPO_ROOT)
decisions.register(mcp, REPO_ROOT)
interactions_events.register(mcp, REPO_ROOT)
gui_tooling.register(mcp, REPO_ROOT)
error_logs.register(mcp)

if __name__ == "__main__":
    mcp.run()
