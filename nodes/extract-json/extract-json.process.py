from typing import Any
import re
import json


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    text = inputs.get("text")
    return_all = inputs.get("return_all") if inputs.get("return_all") is not None else False

    if not isinstance(text, str) or text.strip() == "":
        return {"json": None, "found": False, "raw_match": None}

    def try_parse(s):
        try:
            return {"success": True, "value": json.loads(s), "raw": s}
        except (json.JSONDecodeError, TypeError):
            return {"success": False}

    results = []

    # Strategy 1: Try parsing the entire text as JSON
    direct = try_parse(text.strip())
    if direct["success"]:
        if not return_all:
            return {"json": direct["value"], "found": True, "raw_match": direct["raw"]}
        results.append(direct)

    # Strategy 2: Extract from markdown code blocks (```json or ```)
    code_block_regex = r"```(?:json)?\s*([\s\S]*?)```"
    for match in re.finditer(code_block_regex, text):
        content = match.group(1).strip()
        parsed = try_parse(content)
        if parsed["success"]:
            if not return_all:
                return {"json": parsed["value"], "found": True, "raw_match": parsed["raw"]}
            # Avoid duplicates
            if not any(r["raw"] == parsed["raw"] for r in results):
                results.append(parsed)

    # Strategy 3: Find JSON objects {...} and arrays [...] in text
    # Collect all candidates with their positions, then process in order
    object_regex = r"\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}"
    array_regex = r"\[(?:[^\[\]]|\[(?:[^\[\]]|\[[^\[\]]*\])*\])*\]"

    candidates = []

    for match in re.finditer(object_regex, text):
        candidates.append({"str": match.group(0), "index": match.start()})
    for match in re.finditer(array_regex, text):
        candidates.append({"str": match.group(0), "index": match.start()})

    # Sort by position, then by length (longer first to prefer outer structures)
    candidates.sort(key=lambda c: (c["index"], -len(c["str"])))

    # Filter out candidates that are substrings of earlier valid matches
    used_ranges = []
    for candidate in candidates:
        start = candidate["index"]
        end = start + len(candidate["str"])

        # Skip if this is inside a previously matched range
        is_inside_previous = any(
            start >= r["start"] and end <= r["end"] for r in used_ranges
        )
        if is_inside_previous:
            continue

        parsed = try_parse(candidate["str"])
        if parsed["success"]:
            used_ranges.append({"start": start, "end": end})
            if not return_all:
                return {"json": parsed["value"], "found": True, "raw_match": parsed["raw"]}
            if not any(r["raw"] == parsed["raw"] for r in results):
                results.append(parsed)

    if len(results) == 0:
        return {"json": None, "found": False, "raw_match": None}

    if return_all:
        return {
            "json": [r["value"] for r in results],
            "found": True,
            "raw_match": results[0]["raw"],
        }

    return {"json": results[0]["value"], "found": True, "raw_match": results[0]["raw"]}
