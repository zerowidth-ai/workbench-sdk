from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    text = inputs.get("text")
    max_length = inputs.get("max_length")
    position = inputs.get("position") if inputs.get("position") is not None else "end"
    suffix = inputs.get("suffix") if inputs.get("suffix") is not None else "..."
    word_boundary = inputs.get("word_boundary") if inputs.get("word_boundary") is not None else False

    if not isinstance(text, str):
        return {"text": "", "was_truncated": False, "original_length": 0}

    original_length = len(text)

    if original_length <= max_length:
        return {"text": text, "was_truncated": False, "original_length": original_length}

    suffix_length = len(suffix)
    available_length = max_length - suffix_length

    if available_length <= 0:
        return {"text": suffix[:max_length], "was_truncated": True, "original_length": original_length}

    result = ""

    if position == "end":
        truncated = text[:available_length]

        if word_boundary:
            last_space = truncated.rfind(" ")
            if last_space > available_length * 0.5:
                truncated = truncated[:last_space]

        result = truncated + suffix

    elif position == "start":
        truncated = text[-available_length:]

        if word_boundary:
            first_space = truncated.find(" ")
            if 0 < first_space < available_length * 0.5:
                truncated = truncated[first_space + 1:]

        result = suffix + truncated

    elif position == "middle":
        half_length = (available_length - suffix_length) // 2
        start_part = text[:half_length]
        end_part = text[-half_length:]

        if word_boundary:
            start_last_space = start_part.rfind(" ")
            if start_last_space > half_length * 0.5:
                start_part = start_part[:start_last_space]

            end_first_space = end_part.find(" ")
            if 0 < end_first_space < half_length * 0.5:
                end_part = end_part[end_first_space + 1:]

        result = start_part + suffix + end_part

    else:
        result = text[:available_length] + suffix

    # Ensure we don't exceed max length
    if len(result) > max_length:
        result = result[:max_length]

    return {"text": result, "was_truncated": True, "original_length": original_length}
