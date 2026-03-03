from typing import Any
import re


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    text = inputs.get("text")
    separator = inputs.get("separator") if inputs.get("separator") is not None else r"\n\n"
    default_role = inputs.get("default_role") if inputs.get("default_role") is not None else "user"

    if not isinstance(text, str) or text.strip() == "":
        return {"messages": [], "message_count": 0}

    # Split by separator
    chunks = re.split(separator, text)
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]

    # Role detection pattern - matches "Role:" or "ROLE:" at start of text
    role_pattern = re.compile(r"^(user|assistant|system|human|ai|bot):\s*", re.IGNORECASE)

    messages = []

    for chunk in chunks:
        trimmed = chunk.strip()
        if not trimmed:
            continue

        match = role_pattern.match(trimmed)

        role = default_role
        content = trimmed

        if match:
            detected_role = match.group(1).lower()
            # Normalize role names
            if detected_role == "human":
                role = "user"
            elif detected_role in ("ai", "bot"):
                role = "assistant"
            else:
                role = detected_role
            content = trimmed[match.end():].strip()

        if content:
            messages.append({"role": role, "content": content})

    return {
        "messages": messages,
        "message_count": len(messages),
    }
