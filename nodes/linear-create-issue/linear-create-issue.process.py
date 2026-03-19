"""
Linear Create Issue Node - Create a new issue in Linear.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    linear = config.get("integrations", {}).get("linear")
    if not linear:
        raise Exception("Linear integration not configured. Add your Linear API key to config.keys.linear")

    if not inputs.get("team_id"):
        raise Exception("team_id is required")
    if not inputs.get("title"):
        raise Exception("title is required")

    result = await linear.create_issue(
        inputs["team_id"],
        inputs["title"],
        description=inputs.get("description"),
        priority=inputs.get("priority"),
        assignee_id=inputs.get("assignee_id"),
        label_ids=inputs.get("label_ids"),
    )

    issue = result.get("issue", {})

    return {
        "issue": issue,
        "identifier": issue.get("identifier"),
        "url": issue.get("url"),
    }
