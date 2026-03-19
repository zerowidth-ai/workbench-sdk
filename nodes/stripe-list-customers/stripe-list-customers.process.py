"""
Stripe List Customers Node - List customers from Stripe.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    stripe = config.get("integrations", {}).get("stripe")
    if not stripe:
        raise Exception("Stripe integration not configured. Add your Stripe secret key to config.keys.stripe")

    result = await stripe.list_customers(
        email=inputs.get("email"),
        limit=inputs.get("limit", 10),
        starting_after=inputs.get("starting_after"),
    )

    customers = result.get("data", [])

    return {
        "customers": customers,
        "has_more": result.get("has_more", False),
        "count": len(customers),
    }
