"""
Notion Create Page Node - Create a new page in Notion.
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
    Process function for the Notion Create Page node.
    """
    # Get Notion integration
    integrations = config.get("integrations", {})
    notion = integrations.get("notion")

    if not notion:
        raise Exception(
            "Notion integration not configured. Add your Notion API key to config.keys.notion"
        )

    # Get required inputs
    parent_type = inputs.get("parent_type")
    parent_id = inputs.get("parent_id")
    properties = inputs.get("properties")

    if not parent_type:
        raise Exception("parent_type is required ('database_id' or 'page_id')")
    if parent_type not in ("database_id", "page_id"):
        raise Exception("parent_type must be 'database_id' or 'page_id'")
    if not parent_id:
        raise Exception("parent_id is required")
    if not properties:
        raise Exception("properties is required")

    # Build parent object
    parent = {parent_type: parent_id}

    # Create the page
    page = await notion.create_page(
        parent=parent,
        properties=properties,
        children=inputs.get("children"),
        icon=inputs.get("icon"),
        cover=inputs.get("cover"),
    )

    return {
        "page": page,
        "id": page.get("id"),
        "url": page.get("url"),
    }
