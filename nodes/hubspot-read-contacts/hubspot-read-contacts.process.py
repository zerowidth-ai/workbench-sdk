"""
HubSpot Read Contacts Node - Read contacts from HubSpot CRM.
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
    Process function for the HubSpot Read Contacts node.
    """
    # Get HubSpot integration
    integrations = config.get("integrations", {})
    hubspot = integrations.get("hubspot")

    if not hubspot:
        raise Exception("HubSpot integration not found")

    # Build query parameters
    params = {}

    # Add limit if provided
    limit = inputs.get("limit")
    if limit is not None:
        params["limit"] = limit

    # Add after (paging cursor) if provided
    after = inputs.get("after")
    if after:
        params["after"] = after

    # Handle properties - convert to comma-separated string if needed
    properties = inputs.get("properties")
    if properties:
        if isinstance(properties, list):
            params["properties"] = ",".join(properties)
        elif isinstance(properties, str):
            params["properties"] = properties

    # Handle associations - convert to comma-separated string if needed
    associations = inputs.get("associations")
    if associations:
        if isinstance(associations, list):
            params["associations"] = ",".join(associations)
        elif isinstance(associations, str):
            params["associations"] = associations

    # Make API request
    response = await hubspot.get("/crm/v3/objects/contacts", params)

    # Extract results and paging information
    contacts = response.get("results", [])
    paging = response.get("paging", {})
    next_paging = paging.get("next", {})
    prev_paging = paging.get("prev", {})

    return {
        "contacts": contacts,
        "paging_next_after": next_paging.get("after"),
        "paging_next_link": next_paging.get("link"),
        "paging_prev_before": prev_paging.get("before"),
        "paging_prev_link": prev_paging.get("link"),
    }
