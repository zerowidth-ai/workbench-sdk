"""
Confluence Get Page Node - Retrieve a page by ID.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    confluence = config.get("integrations", {}).get("confluence")
    if not confluence:
        raise Exception("Confluence integration not configured. Add your Confluence config to config.keys.confluence ({email, api_token, domain})")

    if not inputs.get("page_id"):
        raise Exception("page_id is required")

    page = await confluence.get_page(
        inputs["page_id"],
        body_format=inputs.get("body_format", "storage"),
    )

    fmt = inputs.get("body_format", "storage")
    body_section = page.get("body", {}).get(fmt, {})
    body_content = body_section.get("value", "") or body_section.get("representation", "")

    return {
        "page": page,
        "title": page.get("title", ""),
        "body": body_content,
    }
