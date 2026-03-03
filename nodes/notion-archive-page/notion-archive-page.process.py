"""
Notion Archive Page Node - Archive or restore a Notion page.
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
    Process function for the Notion Archive Page node.
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

    # Default to archiving if not specified
    archived = inputs.get("archived", True)

    # Archive or restore the page
    page = await notion.archive_page(page_id, archived=archived)

    return {
        "page": page,
        "id": page.get("id"),
        "archived": page.get("archived", False),
    }
