"""
Notion Get Page Node - Retrieve a page by ID from Notion.
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
    Process function for the Notion Get Page node.
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
    if not page_id:
        raise Exception("page_id is required")

    # Get the page
    page = await notion.get_page(page_id)

    return {
        "page": page,
        "id": page.get("id"),
        "properties": page.get("properties", {}),
        "created_time": page.get("created_time"),
        "last_edited_time": page.get("last_edited_time"),
        "archived": page.get("archived", False),
    }
