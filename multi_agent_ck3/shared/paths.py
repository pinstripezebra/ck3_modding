import pathlib
from functools import lru_cache

from dotenv import load_dotenv

# ── Root paths ─────────────────────────────────────────────────────────────
# multi_agent_ck3/ lives inside ai_dev/, so parent.parent == ai_dev/
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO_ROOT = _PROJECT_ROOT.parent

# Reuse existing ck3_agent artefacts so we don't duplicate large data stores
OUTPUT_DIR = REPO_ROOT / "ck3_agent" / "output"
CHROMA_DIR = str(REPO_ROOT / "ck3_agent" / "chroma_db")

CK3_GAME_DIR = pathlib.Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game"
)


@lru_cache(maxsize=1)
def get_vectorstore():
    """Lazy-initialise the Chroma vectorstore (cached after first call)."""
    load_dotenv(REPO_ROOT / ".env", override=True)
    from langchain_openai import OpenAIEmbeddings
    from langchain_chroma import Chroma

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
