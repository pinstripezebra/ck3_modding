# CK3 Agent MCP Server Setup

## Overview

An MCP (Model Context Protocol) server that exposes a `retrieve_docs` tool, allowing coding models (e.g. GitHub Copilot) to query the local Chroma vector store for CK3 modding documentation.

## Project Structure

```
ck3_agent/
  src/
    main.py                ← MCP server (exposes tools to your coding model)
    load_documentation.py  ← one-time pipeline to populate chroma
  chroma_db/               ← shared persistent vector store
  mcp_setup.md             ← this file
```

## Prerequisites

### 1. Install dependencies

```powershell
pip install mcp fastmcp langchain-chroma langchain-openai langchain-community langchain-text-splitters python-dotenv
```

### 2. Environment variables

Add to your `.env` file at the workspace root:

```
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=github_pat_...   # optional, avoids GitHub rate limits
```

### 3. Populate the vector store

Run this once (or whenever the wiki repo is updated):

```powershell
python c:\dev\ai_dev\ck3_agent\src\load_documentation.py
```

This fetches all `.md` files from `jesec/ck3-modding-wiki`, splits them into chunks, embeds them via `text-embedding-3-small`, and persists them to `ck3_agent/chroma_db/`.

---

## MCP Server (`main.py`)

The server uses **FastMCP** (official MCP Python SDK) wrapping the LangChain Chroma vectorstore.

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ck3-docs")

@mcp.tool()
def retrieve_docs(query: str, k: int = 5) -> str:
    """Retrieve relevant CK3 modding documentation."""
    ...

mcp.run()  # communicates over stdio
```

The server is spawned on demand by the MCP client (VS Code) over stdin/stdout — no port, no network, no daemon required.

---

## VS Code Configuration

Create `.vscode/mcp.json` in the workspace root:

```json
{
  "servers": {
    "ck3-docs": {
      "type": "stdio",
      "command": "c:\\dev\\ai_dev\\.venv\\Scripts\\python.exe",
      "args": ["c:\\dev\\ai_dev\\ck3_agent\\src\\main.py"]
    }
  }
}
```

After saving, VS Code will detect the server. Enable it via the MCP panel or Copilot settings. The `retrieve_docs` tool will then be available to Copilot and other MCP-aware models.

---

## How It Works at Runtime

```
Coding model
    │  calls retrieve_docs("how do events work?")
    ▼
MCP server (main.py via stdio)
    │  embeds query via OpenAI → cosine similarity search
    ▼
ck3_agent/chroma_db/ (local files, no server)
    │  returns top-k matching chunks
    ▼
Model receives context → generates answer
```

## Updating the Vector Store

If the wiki repo updates, re-run the pipeline. The existing `chroma_db` will be overwritten:

```powershell
python c:\dev\ai_dev\ck3_agent\src\load_documentation.py
```

To add deduplication (skip already-indexed files), track file hashes before calling `vectorstore.add_documents()`.
