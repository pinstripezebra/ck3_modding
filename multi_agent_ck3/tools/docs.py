def register(mcp, vectorstore):
    @mcp.tool()
    def retrieve_docs(query: str, k: int = 5) -> str:
        """Retrieve relevant CK3 modding documentation from the vector store."""
        results = vectorstore.similarity_search(query, k=k)
        return "\n\n---\n\n".join(doc.page_content for doc in results)

# -- LangChain tool factory -------------------------------------------------

class _ToolCollector:
    """Mimics FastMCP so register() populates tools without a real server."""
    def __init__(self):
        self._fns: list = []
    def tool(self, **_):
        def _wrap(fn):
            self._fns.append(fn)
            return fn
        return _wrap


def get_tools(vectorstore) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
    collector = _ToolCollector()
    register(collector, vectorstore)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
