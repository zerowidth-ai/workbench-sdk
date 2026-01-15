"""
HubSpot Search Contacts Node - Search contacts in HubSpot CRM.
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
    Process function for the HubSpot Search Contacts node.
    """
    # Get HubSpot integration
    integrations = config.get("integrations", {})
    hubspot = integrations.get("hubspot")

    if not hubspot:
        raise Exception("HubSpot integration not found")

    # Build request body
    body = {
        "query": inputs.get("query"),
    }

    # Add properties - convert to array if needed
    properties = inputs.get("properties")
    if properties is not None:
        if isinstance(properties, list):
            body["properties"] = properties
        elif isinstance(properties, str):
            body["properties"] = [p.strip() for p in properties.split(",") if p.strip()]

    # Add limit if provided
    limit = inputs.get("limit")
    if limit is not None:
        body["limit"] = min(int(limit), 200)  # Cap at 200 as per API

    # Add after (paging cursor) if provided
    after = inputs.get("after")
    if after:
        body["after"] = after

    # Add sorts - convert to array if needed
    sorts = inputs.get("sorts")
    if sorts is not None:
        if isinstance(sorts, list):
            body["sorts"] = sorts
        elif isinstance(sorts, str):
            body["sorts"] = [s.strip() for s in sorts.split(",") if s.strip()]

    # Add filterGroups if provided
    filter_groups = inputs.get("filter_groups")
    if filter_groups and isinstance(filter_groups, list):
        body["filterGroups"] = filter_groups

    # Make API request (POST)
    response = await hubspot.post("/crm/v3/objects/contacts/search", body)

    # Extract results and paging information
    contacts = response.get("results", [])
    total = response.get("total", 0)
    paging = response.get("paging", {})
    next_paging = paging.get("next", {})
    prev_paging = paging.get("prev", {})

    return {
        "contacts": contacts,
        "total": total,
        "paging_next_after": next_paging.get("after"),
        "paging_next_link": next_paging.get("link"),
        "paging_prev_before": prev_paging.get("before"),
        "paging_prev_link": prev_paging.get("link"),
    }
