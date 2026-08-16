# RAG Data Storage Architecture

## Architecture Overview

```
GitHub Repo → parse_repo tool → chunk + embed → store_docs tool → Vector Store → retrieve_docs tool → LLM Agent
```

---

## 1. Parsing Tool

Use **LangChain's `GithubFileLoader`** or raw GitHub API. LangChain has a built-in loader:

```python
from langchain_community.document_loaders import GithubFileLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

@tool
def parse_repo(repo: str, file_filter: str = ".md|.py|.txt") -> str:
    """Parse files from a GitHub repository into chunks."""
    loader = GithubFileLoader(
        repo=repo,  # e.g. "owner/repo"
        access_token=os.environ["GITHUB_TOKEN"],
        github_api_url="https://api.github.com",
        file_filter=lambda path: any(path.endswith(ext) for ext in file_filter.split("|"))
    )
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    return splitter.split_documents(docs)
```

---

## 2. Storage Options — Recommendation Matrix

| Option | Best For | Pros | Cons |
|---|---|---|---|
| **Chroma** (local) | Dev/prototyping | Zero infra, persistent, free | Not distributed |
| **LanceDB** | Local + serverless | Embedded, fast, columnar storage | Newer ecosystem |
| **Pinecone** | Production cloud | Fully managed, scalable, great SDK | Cost at scale |
| **Qdrant** | Self-hosted prod | Best performance, hybrid search | Requires server |
| **pgvector** | If using Postgres | Reuse existing DB, SQL + vectors | Requires Postgres |

### Recommendation for this stack:
- **Chroma** for local development (zero setup, persistent to disk)
- **Pinecone** or **Qdrant Cloud** for production (both have free tiers)

---

## 3. Store + Retrieve Tools (using Chroma as example)

```python
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")  # most cost-efficient
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

@tool
def store_docs(repo: str) -> str:
    """Parse a GitHub repo and store its contents in the vector store."""
    chunks = parse_repo.invoke(repo)  # reuse the parse tool
    vectorstore.add_documents(chunks)
    return f"Stored {len(chunks)} chunks from {repo}"

@tool
def retrieve_docs(query: str, k: int = 5) -> str:
    """Retrieve relevant documentation from the vector store."""
    results = vectorstore.similarity_search(query, k=k)
    return "\n\n---\n\n".join(doc.page_content for doc in results)
```

---

## Key Efficiency Considerations

**Embedding model**: Use `text-embedding-3-small` (OpenAI) — it's ~5x cheaper than `ada-002` with better performance, or use a local model via `sentence-transformers` for zero cost.

**Chunking strategy**: `RecursiveCharacterTextSplitter` with `chunk_size=1000, chunk_overlap=100` works well for mixed code/docs. For pure code, consider `chunk_size=500`.

**Avoid re-embedding**: Track file hashes so `store_docs` skips already-indexed files.

**Hybrid search**: If your data mixes structured/unstructured content, Qdrant's hybrid search (dense + sparse BM25) significantly outperforms pure semantic search.

---

## Recommended Stack

Given the project uses LangGraph + OpenAI:
1. **Parse**: `GithubFileLoader` + `RecursiveCharacterTextSplitter`
2. **Store/Retrieve**: **Chroma** (dev) → swap to **Pinecone** (prod) via LangChain's unified `VectorStore` interface — the tool code stays identical

### Install

```bash
pip install langchain-chroma langchain-community langchain-openai pygithub
```
