"""
Resend Send Email Node - Send an email via Resend.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    resend = config.get("integrations", {}).get("resend")
    if not resend:
        raise Exception("Resend integration not configured. Add your Resend API key to config.keys.resend")

    if not inputs.get("to"):
        raise Exception("to is required")
    if not inputs.get("from"):
        raise Exception("from is required")
    if not inputs.get("subject"):
        raise Exception("subject is required")
    if not inputs.get("text") and not inputs.get("html"):
        raise Exception("Either text or html body is required")

    result = await resend.send_email(
        to=inputs["to"],
        from_email=inputs["from"],
        subject=inputs["subject"],
        text=inputs.get("text"),
        html=inputs.get("html"),
        reply_to=inputs.get("reply_to"),
        cc=inputs.get("cc"),
        bcc=inputs.get("bcc"),
    )

    return {
        "id": result.get("id") if result else None,
    }
