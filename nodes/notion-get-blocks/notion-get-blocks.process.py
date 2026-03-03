"""
Notion Get Blocks Node - Get children blocks of a Notion page or block.
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
    Process function for the Notion Get Blocks node.
    """
    # Get Notion integration
    integrations = config.get("integrations", {})
    notion = integrations.get("notion")

    if not notion:
        raise Exception(
            "Notion integration not configured. Add your Notion API key to config.keys.notion"
        )

    # Get required inputs
    block_id = inputs.get("block_id")
    if not block_id:
        raise Exception("block_id is required")

    # Get block children
    response = await notion.get_block_children(
        block_id=block_id,
        start_cursor=inputs.get("start_cursor"),
        page_size=inputs.get("page_size"),
    )

    return {
        "results": response.get("results", []),
        "has_more": response.get("has_more", False),
        "next_cursor": response.get("next_cursor"),
    }
