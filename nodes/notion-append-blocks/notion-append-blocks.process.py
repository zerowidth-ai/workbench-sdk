"""
Notion Append Blocks Node - Append block content to a Notion page or block.
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
    Process function for the Notion Append Blocks node.
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
    children = inputs.get("children")

    if not block_id:
        raise Exception("block_id is required")
    if not children:
        raise Exception("children is required")
    if not isinstance(children, list):
        raise Exception("children must be an array of block objects")

    # Append blocks
    response = await notion.append_block_children(
        block_id=block_id,
        children=children,
        after=inputs.get("after"),
    )

    return {
        "results": response.get("results", []),
    }
