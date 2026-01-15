"""
Semantic Search Node - Performs semantic search using embeddings.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Semantic Search node.
    """
    try:
        # Get knowledge base and OpenAI integrations
        integrations = config.get("integrations", {})
        knowledge_base = integrations.get("knowledgeBase") or integrations.get("sqlite")
        openai = integrations.get("openai")

        if not knowledge_base:
            raise ValueError(
                "Knowledge base integration not found. Make sure a knowledge database is available."
            )

        if not openai:
            raise ValueError(
                "OpenAI integration not found. Semantic search requires OpenAI API key for embeddings."
            )

        query = inputs.get("query")
        limit = inputs.get("limit", 10)
        similarity_threshold = inputs.get("similarity_threshold", 0.7)
        document_id = inputs.get("document_id")

        embedding_model = settings.get("embedding_model")

        if not query or not isinstance(query, str):
            raise ValueError("Query is required and must be a string")

        # Get the embedding model to use
        model_to_use = embedding_model
        if not model_to_use:
            try:
                model_to_use = await knowledge_base.getEmbeddingModel()
            except Exception:
                model_to_use = "text-embedding-3-small"

        # Create embedding for the query
        embedding_response = await openai.createEmbedding(query, model_to_use)
        query_embedding = embedding_response["data"][0]["embedding"]

        # Perform semantic search
        search_options = {
            "limit": limit,
            "similarity_threshold": similarity_threshold,
            "document_id": document_id,
            "embedding_model": model_to_use,
            "query_embedding": query_embedding,
        }

        results = await knowledge_base.semanticSearch(query, search_options)

        return {
            "results": results,
            "count": len(results),
            "success": True,
            "error": None,
        }

    except Exception as e:
        # Return error information instead of throwing to prevent engine crash
        return {
            "results": [],
            "count": 0,
            "success": False,
            "error": str(e),
        }
