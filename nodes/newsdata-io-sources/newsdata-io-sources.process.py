"""
NewsData.io Sources Node - Fetches available news sources.
"""

from typing import Any


def string_to_array(value):
    """Convert a string to an array, splitting by comma if needed."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value] if value is not None else []


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the NewsData.io Sources node.
    """
    # Get NewsData.io integration from engine
    integrations = config.get("integrations", {})
    newsdata = integrations.get("newsdata_io")

    if not newsdata:
        raise ValueError("NewsData.io integration not found")

    # Process parameters with array handling
    params = {}

    # Handle string inputs that can be arrays
    array_fields = ["countries", "categories", "languages"]

    for field in array_fields:
        if inputs.get(field) is not None:
            params[field] = string_to_array(inputs[field])

    # Handle other parameters with snake_case to API format conversion
    param_mappings = {"priority_domain": "prioritydomain"}

    for input_key, api_key in param_mappings.items():
        if inputs.get(input_key) is not None:
            params[api_key] = inputs[input_key]

    # Process parameters for API call
    processed_params = newsdata.process_params(params)

    # Make API request
    response = await newsdata.get_sources(processed_params)

    results = response.get("results", [])
    return {
        "sources": results,
        "total_sources": len(results),
    }
