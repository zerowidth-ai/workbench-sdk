"""
Firecrawl Scrape Node - Scrapes a URL using the Firecrawl API.
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
    Process function for the Firecrawl Scrape node.
    """
    # Get Firecrawl integration from engine
    integrations = config.get("integrations", {})
    firecrawl = integrations.get("firecrawl")

    if not firecrawl:
        raise Exception("Firecrawl integration not found")

    # Build parameters
    params = {}

    # Handle array fields
    array_fields = ["formats", "include_tags", "exclude_tags"]
    for field in array_fields:
        value = inputs.get(field)
        if value is not None:
            if isinstance(value, str):
                params[field] = [v.strip() for v in value.split(",") if v.strip()]
            elif isinstance(value, list):
                params[field] = value

    # Parameter mappings (snake_case to camelCase)
    param_mappings = {
        "url": "url",
        "formats": "formats",
        "only_main_content": "onlyMainContent",
        "include_tags": "includeTags",
        "exclude_tags": "excludeTags",
        "max_age": "maxAge",
        "wait_for": "waitFor",
        "mobile_device": "mobile",
        "skip_tls_verification": "skipTlsVerification",
        "timeout": "timeout",
        "remove_base64_images": "removeBase64Images",
        "block_ads": "blockAds",
        "proxy": "proxy",
        "store_in_cache": "storeInCache",
        "zero_data_retention": "zeroDataRetention",
    }

    for input_key, api_key in param_mappings.items():
        value = inputs.get(input_key)
        if value is not None:
            params[api_key] = value

    # Make API request
    response = await firecrawl.scrape(params)

    # Extract data from response
    data = response.get("data", {})
    metadata = data.get("metadata", {})

    return {
        "success": response.get("success", False),
        "markdown": data.get("markdown"),
        "html": data.get("html"),
        "raw_html": data.get("rawHtml"),
        "links": data.get("links", []),
        "screenshot": data.get("screenshot"),
        "summary": data.get("summary"),
        "metadata": metadata,
        "status_code": metadata.get("statusCode"),
        "warning": data.get("warning"),
    }
