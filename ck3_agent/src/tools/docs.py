def register(mcp, vectorstore):
    @mcp.tool()
    def retrieve_docs(query: str, k: int = 5) -> str:
        """Retrieve relevant CK3 modding documentation from the vector store."""
        results = vectorstore.similarity_search(query, k=k)
        return "\n\n---\n\n".join(doc.page_content for doc in results)
