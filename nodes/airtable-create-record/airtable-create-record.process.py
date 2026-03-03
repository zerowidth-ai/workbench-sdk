"""
Airtable Create Record Node - Create a new record in a table.
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
    Process function for the Airtable Create Record node.
    """
    # Get Airtable integration
    integrations = config.get("integrations", {})
    airtable = integrations.get("airtable")

    if not airtable:
        raise Exception("Airtable integration not configured. Add your Airtable API key to config.keys.airtable")

    # Get required inputs
    base_id = inputs.get("base_id")
    table_name = inputs.get("table_name")
    fields = inputs.get("fields")

    if not base_id:
        raise Exception("base_id is required")
    if not table_name:
        raise Exception("table_name is required")
    if not fields:
        raise Exception("fields is required")
    if not isinstance(fields, dict):
        raise Exception("fields must be an object")

    # Get optional inputs
    typecast = inputs.get("typecast", False)

    # Make API request
    record = await airtable.create_record(base_id, table_name, fields, typecast=typecast)

    return {
        "record": record,
        "id": record.get("id"),
        "fields": record.get("fields", {}),
        "created_time": record.get("createdTime"),
    }
