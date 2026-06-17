"""
Cohere: Rerank v3.5 - Rerank node for the zv1 engine.
"""

from typing import Any, Optional


def _to_text(doc: Any, text_field: Optional[str]) -> str:
    """Extract the text to rank from a document (string or object)."""
    if isinstance(doc, str):
        return doc
    if isinstance(doc, dict):
        if text_field and doc.get(text_field) is not None:
            return str(doc[text_field])
        for field in ("content", "text", "document", "page_content", "chunk", "body"):
            if doc.get(field) is not None:
                return str(doc[field])
        import json as _json
        return _json.dumps(doc)
    return str(doc)


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Cohere: Rerank v3.5 rerank node.

    Args:
        inputs: Node inputs containing query and documents to rerank.
        settings: Node settings (unused for rerank nodes).
        config: Engine configuration with integrations and keys.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with reranked results, ordered documents, usage and cost data.
    """
    # Get OpenRouter integration from engine
    openrouter = config.get("integrations", {}).get("openrouter")
    if not openrouter:
        raise RuntimeError("OpenRouter integration not available")

    documents = inputs.get("documents")
    if not isinstance(documents, list):
        raise ValueError("documents must be an array")

    text_field = inputs.get("text_field")
    texts = [_to_text(doc, text_field) for doc in documents]

    params: dict[str, Any] = {}
    if inputs.get("top_n") is not None:
        params["top_n"] = inputs.get("top_n")

    response = await openrouter.rerank(
        model="cohere/rerank-v3.5",
        query=inputs.get("query"),
        documents=texts,
        node_config=node_config,
        engine_config=config,
        **params,
    )

    # Reattach original documents by index, preserving the API's relevance order
    results = [
        {
            "index": r.get("index"),
            "relevance_score": r.get("relevance_score"),
            "document": documents[r.get("index")] if r.get("index") is not None else None,
        }
        for r in (response.get("results") or [])
    ]

    return {
        "results": results,
        "ranked_documents": [r["document"] for r in results],
        "top_document": results[0]["document"] if results else None,
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }