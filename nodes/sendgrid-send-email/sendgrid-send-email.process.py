"""
SendGrid Send Email Node - Send an email via SendGrid.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    integrations = config.get("integrations", {})
    sendgrid = integrations.get("sendgrid")

    if not sendgrid:
        raise Exception("SendGrid integration not configured. Add your SendGrid API key to config.keys.sendgrid")

    to = inputs.get("to")
    from_email = inputs.get("from")
    subject = inputs.get("subject")

    if not to:
        raise Exception("to is required")
    if not from_email:
        raise Exception("from is required")
    if not subject:
        raise Exception("subject is required")
    if not inputs.get("text") and not inputs.get("html"):
        raise Exception("Either text or html body is required")

    await sendgrid.send_email(
        to=to,
        from_email=from_email,
        from_name=inputs.get("from_name"),
        subject=subject,
        text=inputs.get("text"),
        html=inputs.get("html"),
        reply_to=inputs.get("reply_to"),
        cc=inputs.get("cc"),
        bcc=inputs.get("bcc"),
    )

    return {
        "message": "Email accepted for delivery",
    }
