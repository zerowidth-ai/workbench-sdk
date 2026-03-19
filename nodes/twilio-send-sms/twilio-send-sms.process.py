"""
Twilio Send SMS Node - Send an SMS via Twilio.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    twilio = config.get("integrations", {}).get("twilio")
    if not twilio:
        raise Exception("Twilio integration not configured. Add your Twilio config to config.keys.twilio ({account_sid, auth_token})")

    if not inputs.get("to"):
        raise Exception("to is required")
    if not inputs.get("from"):
        raise Exception("from is required")
    if not inputs.get("body"):
        raise Exception("body is required")

    result = await twilio.send_sms(inputs["to"], inputs["from"], inputs["body"])

    return {
        "sid": result.get("sid"),
        "status": result.get("status"),
    }
