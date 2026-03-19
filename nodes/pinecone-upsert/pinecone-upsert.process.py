"""
Pinecone Upsert Node - Insert or update vectors in a Pinecone index.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    pinecone = config.get("integrations", {}).get("pinecone")
    if not pinecone:
        raise Exception("Pinecone integration not configured. Add your Pinecone config to config.keys.pinecone ({api_key, host})")

    vectors = inputs.get("vectors")
    if not vectors:
        raise Exception("vectors is required")
    if not isinstance(vectors, list):
        raise Exception("vectors must be an array")

    result = await pinecone.upsert(vectors, namespace=inputs.get("namespace"))

    return {
        "upserted_count": result.get("upsertedCount", len(vectors)),
    }
