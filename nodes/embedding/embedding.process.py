"""
Embedding - Generic embedding node for the zv1 engine.

The model is an input, so the embedding model can be specified or swapped
from outside the flow rather than baked into the node.
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
    Process function for the generic Embedding node.

    Args:
        inputs: Node inputs containing the text/array to embed, the model, and options.
        settings: Node settings (optional model override).
        config: Engine configuration with integrations and keys.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with embedding, embeddings, dimensions, model, usage and cost data.
    """
    # Get OpenRouter integration from engine
    openrouter = config.get("integrations", {}).get("openrouter")
    if not openrouter:
        raise RuntimeError("OpenRouter integration not available")

    # Model is dynamic — read from input (or settings override), fall back to a default
    model = inputs.get("model") or (settings or {}).get("model") or "openai/text-embedding-3-small"

    if inputs.get("input") is None:
        raise ValueError("input is required")

    # Build optional parameters (only sent when provided)
    params: dict[str, Any] = {}
    if inputs.get("dimensions") is not None:
        params["dimensions"] = inputs.get("dimensions")
    if inputs.get("encoding_format") is not None:
        params["encoding_format"] = inputs.get("encoding_format")

    response = await openrouter.create_embedding(
        model=model,
        input=inputs.get("input"),
        node_config=node_config,
        engine_config=config,
        **params,
    )

    return {
        "embedding": response.get("embedding"),
        "embeddings": response.get("embeddings"),
        "dimensions": response.get("dimensions"),
        "model": response.get("model"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }
