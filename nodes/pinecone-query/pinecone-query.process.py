"""
Pinecone Query Node - Query vectors from a Pinecone index.
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

    vector = inputs.get("vector")
    if not vector:
        raise Exception("vector is required")
    if not isinstance(vector, list):
        raise Exception("vector must be an array of numbers")

    result = await pinecone.query(
        vector,
        top_k=inputs.get("top_k", 10),
        namespace=inputs.get("namespace"),
        filter=inputs.get("filter"),
        include_metadata=inputs.get("include_metadata", True),
        include_values=inputs.get("include_values", False),
    )

    return {
        "matches": result.get("matches", []),
        "namespace": result.get("namespace", ""),
    }
