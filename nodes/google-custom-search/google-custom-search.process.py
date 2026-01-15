"""
Google Custom Search Node - Search using Google Custom Search API.
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
    Process function for the Google Custom Search node.
    """
    # Get Google Custom Search integration from engine
    integrations = config.get("integrations", {})
    google_search = integrations.get("google_custom_search")

    if not google_search:
        raise Exception("Google Custom Search integration not found")

    # Build parameters
    params = {}

    # Handle CX parameter
    cx = inputs.get("cx") or getattr(google_search, "cx", None)
    if not cx:
        raise Exception("Custom Search Engine ID (cx) is required. Please provide it as an input or ensure your key configuration includes a default CX value.")

    params["cx"] = cx

    # Parameter mappings
    param_mappings = {
        "query": "q",
        "num": "num",
        "start": "start",
        "lr": "lr",
        "safe": "safe",
        "gl": "gl",
        "cr": "cr",
        "googlehost": "googlehost",
        "highRange": "highRange",
        "hl": "hl",
        "hq": "hq",
        "imgColorType": "imgColorType",
        "imgDominantColor": "imgDominantColor",
        "imgSize": "imgSize",
        "imgType": "imgType",
        "linkSite": "linkSite",
        "lowRange": "lowRange",
        "orTerms": "orTerms",
        "relatedSite": "relatedSite",
        "rights": "rights",
        "searchType": "searchType",
        "siteSearch": "siteSearch",
        "siteSearchFilter": "siteSearchFilter",
        "sort": "sort",
        "exactTerms": "exactTerms",
        "excludeTerms": "excludeTerms",
        "fileType": "fileType",
        "dateRestrict": "dateRestrict",
    }

    for input_key, api_key in param_mappings.items():
        value = inputs.get(input_key)
        if value is not None:
            params[api_key] = value

    # Special handling for siteSearchFilter
    if params.get("siteSearchFilter") and not params.get("siteSearch"):
        del params["siteSearchFilter"]

    # Make API request
    response = await google_search.search(params)

    # Extract and clean data from response
    raw_items = response.get("items", [])
    search_information = response.get("searchInformation", {})

    # Clean up items
    items = [
        {
            "title": item.get("title"),
            "link": item.get("link"),
            "displayLink": item.get("displayLink"),
            "snippet": item.get("snippet"),
        }
        for item in raw_items
    ]

    return {
        "items": items,
        "searchInformation": search_information,
        "totalResults": search_information.get("totalResults", "0"),
        "searchTime": search_information.get("searchTime", 0),
    }
