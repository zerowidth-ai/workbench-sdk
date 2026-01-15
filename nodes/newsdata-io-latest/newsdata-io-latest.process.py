"""
NewsData.io Latest News Node - Fetches latest news articles.
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
    Process function for the NewsData.io Latest News node.
    """
    # Get NewsData.io integration from engine
    integrations = config.get("integrations", {})
    newsdata = integrations.get("newsdata_io")

    if not newsdata:
        raise ValueError("NewsData.io integration not found")

    # Process parameters with array handling
    params = {}

    # Handle string inputs that can be arrays
    array_fields = [
        "countries",
        "regions",
        "categories",
        "exclude_categories",
        "languages",
        "domains",
        "exclude_domains",
        "exclude_fields",
    ]

    for field in array_fields:
        if inputs.get(field) is not None:
            params[field] = string_to_array(inputs[field])

    # Handle other parameters with snake_case to API format conversion
    param_mappings = {
        "q": "q",
        "q_in_title": "qInTitle",
        "q_in_meta": "qInMeta",
        "domains": "domain",
        "categories": "category",
        "exclude_categories": "excludecategory",
        "languages": "language",
        "exclude_domains": "excludedomain",
        "exclude_fields": "excludefield",
        "priority_domain": "prioritydomain",
        "timeframe": "timeframe",
        "full_content": "full_content",
        "image": "image",
        "video": "video",
        "remove_duplicate": "removeduplicate",
        "size": "size",
    }

    for input_key, api_key in param_mappings.items():
        if inputs.get(input_key) is not None:
            params[api_key] = inputs[input_key]

    # Process parameters for API call
    processed_params = newsdata.process_params(params)

    # Make API request
    response = await newsdata.get_latest(processed_params)

    return {
        "articles": response.get("results", []),
        "total_results": response.get("totalResults", 0),
        "next_page": response.get("nextPage"),
    }
