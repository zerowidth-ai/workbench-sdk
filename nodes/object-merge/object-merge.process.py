from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    objects = inputs.get("objects")
    array_mode = inputs.get("array_mode") if inputs.get("array_mode") is not None else "replace"

    # Normalize to list
    object_list = objects if isinstance(objects, list) else [objects]

    # Filter out non-dicts
    valid_objects = [
        obj for obj in object_list
        if isinstance(obj, dict)
    ]

    if len(valid_objects) == 0:
        return {"merged": {}}

    def is_plain_object(val):
        return isinstance(val, dict)

    def deep_merge(target, source):
        result = {**target}

        for key in source:
            target_val = target.get(key)
            source_val = source[key]

            if isinstance(source_val, list):
                if array_mode == "concat" and isinstance(target_val, list):
                    result[key] = target_val + source_val
                else:
                    result[key] = source_val.copy()
            elif is_plain_object(source_val):
                if is_plain_object(target_val):
                    result[key] = deep_merge(target_val, source_val)
                else:
                    result[key] = deep_merge({}, source_val)
            else:
                result[key] = source_val

        return result

    merged = {}
    for obj in valid_objects:
        merged = deep_merge(merged, obj)

    return {"merged": merged}
