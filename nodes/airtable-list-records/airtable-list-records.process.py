"""
Airtable List Records Node - List and query records from an Airtable table.
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
    Process function for the Airtable List Records node.
    """
    # Get Airtable integration
    integrations = config.get("integrations", {})
    airtable = integrations.get("airtable")

    if not airtable:
        raise Exception("Airtable integration not configured. Add your Airtable API key to config.keys.airtable")

    # Get required inputs
    base_id = inputs.get("base_id")
    table_name = inputs.get("table_name")

    if not base_id:
        raise Exception("base_id is required")
    if not table_name:
        raise Exception("table_name is required")

    # Build optional params
    params = {}
    if inputs.get("filter_formula"):
        params["filter_formula"] = inputs["filter_formula"]
    if inputs.get("sort_field"):
        params["sort_field"] = inputs["sort_field"]
        params["sort_direction"] = inputs.get("sort_direction", "asc")
    if inputs.get("max_records"):
        params["max_records"] = inputs["max_records"]
    if inputs.get("page_size"):
        params["page_size"] = inputs["page_size"]
    if inputs.get("offset"):
        params["offset"] = inputs["offset"]
    if inputs.get("view"):
        params["view"] = inputs["view"]

    # Make API request
    response = await airtable.list_records(base_id, table_name, **params)

    return {
        "records": response.get("records", []),
        "offset": response.get("offset"),
    }
