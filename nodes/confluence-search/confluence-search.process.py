"""
Confluence Search Node - Search pages using CQL.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    confluence = config.get("integrations", {}).get("confluence")
    if not confluence:
        raise Exception("Confluence integration not configured. Add your Confluence config to config.keys.confluence ({email, api_token, domain})")

    if not inputs.get("cql"):
        raise Exception("cql is required")

    result = await confluence.search(
        inputs["cql"],
        limit=inputs.get("limit", 25),
        start=inputs.get("start", 0),
    )

    results = result.get("results", [])

    return {
        "results": results,
        "total_size": result.get("totalSize", 0),
        "count": len(results),
    }
