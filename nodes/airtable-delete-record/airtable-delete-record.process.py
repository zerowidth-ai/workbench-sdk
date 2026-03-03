"""
Airtable Delete Record Node - Delete a record from a table.
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
    Process function for the Airtable Delete Record node.
    """
    # Get Airtable integration
    integrations = config.get("integrations", {})
    airtable = integrations.get("airtable")

    if not airtable:
        raise Exception("Airtable integration not configured. Add your Airtable API key to config.keys.airtable")

    # Get required inputs
    base_id = inputs.get("base_id")
    table_name = inputs.get("table_name")
    record_id = inputs.get("record_id")

    if not base_id:
        raise Exception("base_id is required")
    if not table_name:
        raise Exception("table_name is required")
    if not record_id:
        raise Exception("record_id is required")

    # Make API request
    response = await airtable.delete_record(base_id, table_name, record_id)

    return {
        "deleted": response.get("deleted", False),
        "record_id": response.get("id", record_id),
    }
