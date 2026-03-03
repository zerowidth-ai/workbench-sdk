from typing import Any
import hashlib
import json


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    content = inputs.get("content")
    algorithm = inputs.get("algorithm") if inputs.get("algorithm") is not None else "sha256"

    if isinstance(content, str):
        string_content = content
    elif content is None:
        string_content = ""
    else:
        string_content = json.dumps(content, sort_keys=True)

    if algorithm == "sha256":
        hash_obj = hashlib.sha256(string_content.encode("utf-8"))
    elif algorithm == "sha1":
        hash_obj = hashlib.sha1(string_content.encode("utf-8"))
    elif algorithm == "md5":
        hash_obj = hashlib.md5(string_content.encode("utf-8"))
    else:
        hash_obj = hashlib.sha256(string_content.encode("utf-8"))

    return {"hash": hash_obj.hexdigest()}
