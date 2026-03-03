from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    messages = inputs.get("messages")
    include_system = inputs.get("include_system") if inputs.get("include_system") is not None else False
    separator = inputs.get("separator") if inputs.get("separator") is not None else "\n\n"
    role_format = inputs.get("role_format") if inputs.get("role_format") is not None else "capitalized"

    if not isinstance(messages, list):
        raise Exception("Messages input must be an array")

    def format_role(role):
        if role_format == "none":
            return ""
        if role_format == "uppercase":
            return role.upper()
        if role_format == "lowercase":
            return role.lower()
        # capitalized (default)
        return role.capitalize()

    def get_content(message):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    parts.append(item["text"])
            return " ".join(parts)
        return str(content) if content is not None else ""

    lines = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        if not role:
            continue

        # Skip system messages if not included
        if role == "system" and not include_system:
            continue

        # Skip tool messages (they don't make sense in text transcript)
        if role == "tool":
            continue

        content = get_content(message)
        formatted_role = format_role(role)

        if role_format == "none":
            lines.append(content)
        else:
            lines.append(f"{formatted_role}: {content}")

    return {
        "text": separator.join(lines),
        "message_count": len(lines),
    }
