"""
Jira List Issues Node - Search issues using JQL.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    jira = config.get("integrations", {}).get("jira")
    if not jira:
        raise Exception("Jira integration not configured. Add your Jira config to config.keys.jira ({email, api_token, domain})")

    if not inputs.get("jql"):
        raise Exception("jql is required")

    result = await jira.list_issues(
        inputs["jql"],
        max_results=inputs.get("max_results", 25),
        start_at=inputs.get("start_at", 0),
    )

    issues = result.get("issues", [])

    return {
        "issues": issues,
        "total": result.get("total", 0),
        "count": len(issues),
    }
