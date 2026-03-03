from typing import Any
import re


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    xml = inputs.get("xml")
    remove_root = inputs.get("remove_root") if inputs.get("remove_root") is not None else False

    if not isinstance(xml, str):
        return {"json": None, "success": False, "error": "Input must be a string"}

    if xml.strip() == "":
        return {"json": None, "success": True, "error": None}

    try:
        result = parse_xml(xml.strip())

        if remove_root and result and isinstance(result, dict):
            keys = list(result.keys())
            if len(keys) == 1:
                result = result[keys[0]]

        return {"json": result, "success": True, "error": None}
    except Exception as e:
        return {"json": None, "success": False, "error": str(e)}


def parse_xml(xml: str):
    index = [0]

    def skip_whitespace():
        while index[0] < len(xml) and xml[index[0]].isspace():
            index[0] += 1

    def parse_text():
        text = ""
        while index[0] < len(xml) and xml[index[0]] != "<":
            text += xml[index[0]]
            index[0] += 1
        return decode_entities(text.strip())

    def decode_entities(text):
        return (text
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&quot;", '"')
            .replace("&apos;", "'"))

    def parse_tag_name():
        name = ""
        while index[0] < len(xml) and re.match(r"[a-zA-Z0-9_-]", xml[index[0]]):
            name += xml[index[0]]
            index[0] += 1
        return name

    def parse_element():
        skip_whitespace()

        if index[0] >= len(xml) or xml[index[0]] != "<":
            return parse_text()

        index[0] += 1  # skip <

        # Check for closing tag
        if xml[index[0]] == "/":
            return None

        tag_name = parse_tag_name()
        if not tag_name:
            raise Exception("Invalid XML: expected tag name")

        # Skip attributes (we don't parse them)
        while index[0] < len(xml) and xml[index[0]] not in (">", "/"):
            index[0] += 1

        # Self-closing tag
        if xml[index[0]] == "/":
            index[0] += 2  # skip />
            return {tag_name: None}

        index[0] += 1  # skip >

        # Parse children
        children = []
        text_content = ""

        while index[0] < len(xml):
            skip_whitespace()

            if index[0] >= len(xml):
                break

            # Check for closing tag
            if xml[index[0]] == "<" and index[0] + 1 < len(xml) and xml[index[0] + 1] == "/":
                index[0] += 2
                closing_tag = parse_tag_name()
                if closing_tag != tag_name:
                    raise Exception(f"Mismatched tags: {tag_name} and {closing_tag}")
                while index[0] < len(xml) and xml[index[0]] != ">":
                    index[0] += 1
                index[0] += 1  # skip >
                break

            # Check for child element
            if xml[index[0]] == "<":
                child = parse_element()
                if child is not None:
                    children.append(child)
            else:
                # Text content
                text_content += parse_text()

        # Determine result structure
        if len(children) == 0:
            # Text-only content
            text = text_content.strip()
            if text == "":
                return {tag_name: None}
            if text == "true":
                return {tag_name: True}
            if text == "false":
                return {tag_name: False}
            if re.match(r"^-?\d+$", text):
                return {tag_name: int(text)}
            if re.match(r"^-?\d+\.\d+$", text):
                return {tag_name: float(text)}
            return {tag_name: text}

        # Merge children
        result = {}

        for child in children:
            for key, value in child.items():
                if key in result:
                    # Convert to array
                    if not isinstance(result[key], list):
                        result[key] = [result[key]]
                    result[key].append(value)
                else:
                    result[key] = value

        return {tag_name: result}

    return parse_element()
