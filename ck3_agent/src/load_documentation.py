import os
import pathlib
from dotenv import load_dotenv
from langchain_community.document_loaders import GithubFileLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

"""data pipeline for loading CK3 modding documentation from GitHub, splitting into chunks, and storing in Chroma vector store."""

REPO = "jesec/ck3-modding-wiki"
CHROMA_DIR = str(pathlib.Path(__file__).resolve().parent.parent / "chroma_db")

# --- Parse ---
print(f"Loading files from {REPO}...")
loader = GithubFileLoader(
    repo=REPO,
    access_token=os.environ.get("GITHUB_TOKEN"),
    github_api_url="https://api.github.com",
    branch="master",
    file_filter=lambda path: path.endswith(".md"),
)
docs = loader.load()
print(f"  Loaded {len(docs)} files")

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
chunks = splitter.split_documents(docs)
print(f"  Split into {len(chunks)} chunks")

# --- Store ---
print("\nStoring chunks in Chroma...")
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory=CHROMA_DIR,
)
print(f"  Stored {len(chunks)} chunks to {CHROMA_DIR}")

# --- Retrieve (test) ---
test_queries = [
    "How do I create a new event in CK3?",
    "What is a modifier in CK3 modding?",
    "How do traits work in CK3?",
]

print("\n--- Retrieval Tests ---")
for query in test_queries:
    results = vectorstore.similarity_search(query, k=3)
    print(f"\nQuery: {query}")
    for i, doc in enumerate(results, 1):
        source = doc.metadata.get("source", "unknown")
        preview = doc.page_content[:200].replace("\n", " ")
        print(f"  [{i}] {source}\n      {preview}...")
