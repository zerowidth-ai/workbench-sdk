"""
Notion Update Page Node - Update properties of an existing Notion page.
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
    Process function for the Notion Update Page node.
    """
    # Get Notion integration
    integrations = config.get("integrations", {})
    notion = integrations.get("notion")

    if not notion:
        raise Exception(
            "Notion integration not configured. Add your Notion API key to config.keys.notion"
        )

    # Get required inputs
    page_id = inputs.get("page_id")
    properties = inputs.get("properties")

    if not page_id:
        raise Exception("page_id is required")
    if not properties:
        raise Exception("properties is required")

    # Update the page
    page = await notion.update_page(
        page_id=page_id,
        properties=properties,
        icon=inputs.get("icon"),
        cover=inputs.get("cover"),
    )

    return {
        "page": page,
        "id": page.get("id"),
        "last_edited_time": page.get("last_edited_time"),
    }
