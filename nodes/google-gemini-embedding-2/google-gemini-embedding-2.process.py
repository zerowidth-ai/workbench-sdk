"""
Google: Gemini Embedding 2 - Embedding node for the zv1 engine.
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
    Process function for the Google: Gemini Embedding 2 embedding node.

    Args:
        inputs: Node inputs containing the text/array to embed and options.
        settings: Node settings (unused for embedding nodes).
        config: Engine configuration with integrations and keys.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with embedding, embeddings, dimensions, usage and cost data.
    """
    # Get OpenRouter integration from engine
    openrouter = config.get("integrations", {}).get("openrouter")
    if not openrouter:
        raise RuntimeError("OpenRouter integration not available")

    # Build optional parameters (only sent when provided)
    params: dict[str, Any] = {}
    if inputs.get("dimensions") is not None:
        params["dimensions"] = inputs.get("dimensions")
    if inputs.get("encoding_format") is not None:
        params["encoding_format"] = inputs.get("encoding_format")

    response = await openrouter.create_embedding(
        model="google/gemini-embedding-2",
        input=inputs.get("input"),
        node_config=node_config,
        engine_config=config,
        **params,
    )

    return {
        "embedding": response.get("embedding"),
        "embeddings": response.get("embeddings"),
        "dimensions": response.get("dimensions"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }