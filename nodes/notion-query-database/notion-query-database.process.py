"""
Notion Query Database Node - Query and filter entries from a Notion database.
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
    Process function for the Notion Query Database node.
    """
    # Get Notion integration
    integrations = config.get("integrations", {})
    notion = integrations.get("notion")

    if not notion:
        raise Exception(
            "Notion integration not configured. Add your Notion API key to config.keys.notion"
        )

    # Get required inputs
    database_id = inputs.get("database_id")
    if not database_id:
        raise Exception("database_id is required")

    # Query the database
    response = await notion.query_database(
        database_id=database_id,
        filter=inputs.get("filter"),
        sorts=inputs.get("sorts"),
        start_cursor=inputs.get("start_cursor"),
        page_size=inputs.get("page_size"),
    )

    return {
        "results": response.get("results", []),
        "has_more": response.get("has_more", False),
        "next_cursor": response.get("next_cursor"),
    }
