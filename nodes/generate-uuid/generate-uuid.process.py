from typing import Any
import uuid


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    count = max(1, int(inputs.get("count") or 1))

    uuids = [str(uuid.uuid4()) for _ in range(count)]

    return {
        "uuid": uuids[0],
        "uuids": uuids,
    }
