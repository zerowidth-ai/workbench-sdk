from typing import Any
import re


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    json_input = inputs.get("json")
    root_element = inputs.get("root_element") if inputs.get("root_element") is not None else "root"
    pretty = inputs.get("pretty") if inputs.get("pretty") is not None else True
    indent = inputs.get("indent") if inputs.get("indent") is not None else 2

    def escape_xml(s):
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def to_xml(value, tag_name, depth=0):
        spaces = " " * (indent * depth) if pretty else ""
        newline = "\n" if pretty else ""

        if value is None:
            return f"{spaces}<{tag_name}></{tag_name}>"

        if isinstance(value, bool):
            return f"{spaces}<{tag_name}>{'true' if value else 'false'}</{tag_name}>"

        if isinstance(value, (int, float)):
            return f"{spaces}<{tag_name}>{value}</{tag_name}>"

        if isinstance(value, str):
            return f"{spaces}<{tag_name}>{escape_xml(value)}</{tag_name}>"

        if isinstance(value, list):
            # For arrays, use singular form of tag name for items
            item_tag = tag_name[:-1] if tag_name.endswith("s") else "item"
            items = newline.join(to_xml(item, item_tag, depth + 1) for item in value)
            return f"{spaces}<{tag_name}>{newline}{items}{newline}{spaces}</{tag_name}>"

        if isinstance(value, dict):
            keys = list(value.keys())
            if len(keys) == 0:
                return f"{spaces}<{tag_name}></{tag_name}>"

            children = []
            for key in keys:
                # Sanitize key to be valid XML tag name
                safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
                safe_key = re.sub(r"^(\d)", r"_\1", safe_key)
                children.append(to_xml(value[key], safe_key, depth + 1))

            children_xml = newline.join(children)
            return f"{spaces}<{tag_name}>{newline}{children_xml}{newline}{spaces}</{tag_name}>"

        return f"{spaces}<{tag_name}>{escape_xml(str(value))}</{tag_name}>"

    xml = to_xml(json_input, root_element, 0)

    return {"xml": xml}
