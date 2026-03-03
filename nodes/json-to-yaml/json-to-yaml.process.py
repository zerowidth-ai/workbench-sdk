from typing import Any
import json
import re


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    json_input = inputs.get("json")
    indent = inputs.get("indent") if inputs.get("indent") is not None else 2

    if json_input is None:
        return {"yaml": "null"}

    def to_yaml(value, depth=0):
        spaces = " " * (indent * depth)
        child_spaces = " " * (indent * (depth + 1))

        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, str):
            # Check if string needs quoting
            needs_quotes = (
                value == "" or
                "\n" in value or
                ":" in value or
                "#" in value or
                value.startswith(" ") or
                value.endswith(" ") or
                value in ("true", "false", "null") or
                re.match(r"^[\d.-]+$", value)
            )
            if needs_quotes:
                return json.dumps(value)
            return value

        if isinstance(value, list):
            if len(value) == 0:
                return "[]"

            items = []
            for item in value:
                item_yaml = to_yaml(item, depth)
                if isinstance(item, dict) and len(item) > 0:
                    lines = item_yaml.split("\n")
                    formatted = f"- {lines[0]}"
                    if len(lines) > 1:
                        formatted += "\n" + "\n".join(lines[1:])
                    items.append(formatted)
                else:
                    items.append(f"- {item_yaml}")

            return "\n".join(items)

        if isinstance(value, dict):
            keys = list(value.keys())
            if len(keys) == 0:
                return "{}"

            pairs = []
            for key in keys:
                val = value[key]

                # Check if key needs quoting
                safe_key = key if re.match(r"^[\w-]+$", key) else json.dumps(key)

                if isinstance(val, dict) and len(val) > 0:
                    val_yaml = to_yaml(val, depth + 1)
                    indented = ("\n" + child_spaces).join(val_yaml.split("\n"))
                    pairs.append(f"{safe_key}:\n{child_spaces}{indented}")
                elif isinstance(val, list) and len(val) > 0:
                    val_yaml = to_yaml(val, depth + 1)
                    indented = ("\n" + child_spaces).join(val_yaml.split("\n"))
                    pairs.append(f"{safe_key}:\n{child_spaces}{indented}")
                else:
                    val_yaml = to_yaml(val, depth + 1)
                    pairs.append(f"{safe_key}: {val_yaml}")

            return "\n".join(pairs)

        return str(value)

    yaml_output = to_yaml(json_input)

    return {"yaml": yaml_output}
