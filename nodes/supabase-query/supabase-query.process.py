"""
Supabase Query Node - Query rows from a Supabase table.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    supabase = config.get("integrations", {}).get("supabase")
    if not supabase:
        raise Exception("Supabase integration not configured. Add your Supabase config to config.keys.supabase ({url, key})")

    if not inputs.get("table"):
        raise Exception("table is required")

    rows = await supabase.query(
        inputs["table"],
        select=inputs.get("select", "*"),
        filters=inputs.get("filters"),
        order=inputs.get("order"),
        limit=inputs.get("limit"),
        offset=inputs.get("offset"),
    )

    rows = rows if isinstance(rows, list) else []
    return {
        "rows": rows,
        "count": len(rows),
    }
