"""
Slack Send Message Node - Post a message to a Slack channel.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    slack = config.get("integrations", {}).get("slack")
    if not slack:
        raise Exception("Slack integration not configured. Add your Slack Bot token to config.keys.slack")

    if not inputs.get("channel"):
        raise Exception("channel is required")
    if not inputs.get("text"):
        raise Exception("text is required")

    result = await slack.post_message(
        inputs["channel"],
        inputs["text"],
        thread_ts=inputs.get("thread_ts"),
    )

    return {
        "message": result.get("message"),
        "ts": result.get("ts"),
        "channel": result.get("channel"),
    }
