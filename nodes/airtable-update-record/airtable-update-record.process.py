"""
Airtable Update Record Node - Update an existing record.
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
    Process function for the Airtable Update Record node.
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
    fields = inputs.get("fields")

    if not base_id:
        raise Exception("base_id is required")
    if not table_name:
        raise Exception("table_name is required")
    if not record_id:
        raise Exception("record_id is required")
    if not fields:
        raise Exception("fields is required")
    if not isinstance(fields, dict):
        raise Exception("fields must be an object")

    # Get optional inputs
    typecast = inputs.get("typecast", False)

    # Make API request
    record = await airtable.update_record(base_id, table_name, record_id, fields, typecast=typecast)

    return {
        "record": record,
        "id": record.get("id"),
        "fields": record.get("fields", {}),
        "created_time": record.get("createdTime"),
    }
