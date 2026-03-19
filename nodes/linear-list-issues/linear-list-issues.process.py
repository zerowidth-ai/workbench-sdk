"""
Linear List Issues Node - List issues from Linear.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    linear = config.get("integrations", {}).get("linear")
    if not linear:
        raise Exception("Linear integration not configured. Add your Linear API key to config.keys.linear")

    result = await linear.list_issues(
        first=inputs.get("first", 25),
        after=inputs.get("after"),
        filter=inputs.get("filter"),
    )

    nodes = result.get("nodes", [])
    page_info = result.get("pageInfo", {})

    return {
        "issues": nodes,
        "count": len(nodes),
        "has_more": page_info.get("hasNextPage", False),
        "end_cursor": page_info.get("endCursor"),
    }
