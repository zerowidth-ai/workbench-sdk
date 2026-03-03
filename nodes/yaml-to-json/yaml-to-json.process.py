from typing import Any
import re


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    yaml_input = inputs.get("yaml")

    if not isinstance(yaml_input, str):
        return {"json": None, "success": False, "error": "Input must be a string"}

    if yaml_input.strip() == "":
        return {"json": None, "success": True, "error": None}

    try:
        result = parse_yaml(yaml_input)
        return {"json": result, "success": True, "error": None}
    except Exception as e:
        return {"json": None, "success": False, "error": str(e)}


def parse_yaml(yaml: str):
    lines = yaml.split("\n")
    index = [0]  # Use list to allow mutation in nested function

    def get_indent(line):
        match = re.match(r"^(\s*)", line)
        return len(match.group(1)) if match else 0

    def parse_value(value):
        value = value.strip()

        if value == "" or value == "null" or value == "~":
            return None
        if value == "true":
            return True
        if value == "false":
            return False

        # Quoted string
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1].replace("\\n", "\n").replace('\\"', '"')

        # Number
        if re.match(r"^-?\d+$", value):
            return int(value)
        if re.match(r"^-?\d+\.\d+$", value):
            return float(value)

        # Empty object/array
        if value == "{}":
            return {}
        if value == "[]":
            return []

        return value

    def parse_block(min_indent):
        result = {}
        is_array = None
        array_result = []

        while index[0] < len(lines):
            line = lines[index[0]]

            # Skip empty lines and comments
            if line.strip() == "" or line.strip().startswith("#"):
                index[0] += 1
                continue

            indent = get_indent(line)

            # If we've dedented, we're done with this block
            if indent < min_indent:
                break

            trimmed = line.strip()

            # Array item
            if trimmed.startswith("- "):
                if is_array is False:
                    raise Exception("Mixed array and object syntax")
                is_array = True

                content = trimmed[2:]

                # Check if it's a key-value on same line as dash
                if ": " in content:
                    colon_pos = content.index(": ")
                    key = content[:colon_pos]
                    value = content[colon_pos + 2:]

                    index[0] += 1
                    child_indent = indent + 2

                    # Check if there are more keys at the child indent level
                    obj = {key: parse_value(value)}

                    while index[0] < len(lines):
                        next_line = lines[index[0]]
                        if next_line.strip() == "" or next_line.strip().startswith("#"):
                            index[0] += 1
                            continue
                        next_indent = get_indent(next_line)
                        if next_indent < child_indent or next_line.strip().startswith("- "):
                            break
                        if next_indent == child_indent:
                            next_trimmed = next_line.strip()
                            if ": " in next_trimmed:
                                next_colon_pos = next_trimmed.index(": ")
                                next_key = next_trimmed[:next_colon_pos]
                                next_value = next_trimmed[next_colon_pos + 2:]
                                obj[next_key] = parse_value(next_value)
                                index[0] += 1
                            else:
                                break
                        else:
                            break

                    array_result.append(obj)
                else:
                    index[0] += 1
                    array_result.append(parse_value(content))
                continue

            # Key-value pair
            if ": " in trimmed:
                if is_array is True:
                    raise Exception("Mixed array and object syntax")
                is_array = False

                colon_pos = trimmed.index(": ")
                key = trimmed[:colon_pos]
                value = trimmed[colon_pos + 2:]

                index[0] += 1

                if value == "" or value == "|" or value == ">":
                    # Nested block
                    next_indent = get_indent(lines[index[0]]) if index[0] < len(lines) else indent
                    if next_indent > indent and index[0] < len(lines) and not lines[index[0]].strip().startswith("#"):
                        result[key] = parse_block(next_indent)
                    else:
                        result[key] = None
                else:
                    result[key] = parse_value(value)
                continue

            # Key without value (nested object follows)
            if trimmed.endswith(":"):
                if is_array is True:
                    raise Exception("Mixed array and object syntax")
                is_array = False

                key = trimmed[:-1]
                index[0] += 1

                next_indent = get_indent(lines[index[0]]) if index[0] < len(lines) else indent
                if next_indent > indent:
                    result[key] = parse_block(next_indent)
                else:
                    result[key] = None
                continue

            index[0] += 1

        return array_result if is_array else result

    return parse_block(0)
