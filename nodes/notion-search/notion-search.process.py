"""
Notion Search Node - Search pages and databases in a Notion workspace.
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
    Process function for the Notion Search node.
    """
    # Get Notion integration
    integrations = config.get("integrations", {})
    notion = integrations.get("notion")

    if not notion:
        raise Exception(
            "Notion integration not configured. Add your Notion API key to config.keys.notion"
        )

    # Build filter if filter_type is specified
    filter_obj = None
    if inputs.get("filter_type"):
        filter_obj = {"value": inputs["filter_type"], "property": "object"}

    # Build sort if specified
    sort_obj = None
    if inputs.get("sort_direction") or inputs.get("sort_timestamp"):
        sort_obj = {
            "direction": inputs.get("sort_direction", "descending"),
            "timestamp": inputs.get("sort_timestamp", "last_edited_time"),
        }

    # Search
    response = await notion.search(
        query=inputs.get("query"),
        filter=filter_obj,
        sort=sort_obj,
        start_cursor=inputs.get("start_cursor"),
        page_size=inputs.get("page_size"),
    )

    return {
        "results": response.get("results", []),
        "has_more": response.get("has_more", False),
        "next_cursor": response.get("next_cursor"),
    }
