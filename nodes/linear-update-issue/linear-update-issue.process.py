"""
Linear Update Issue Node - Update an existing issue in Linear.
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

    if not inputs.get("issue_id"):
        raise Exception("issue_id is required")

    updates: dict[str, Any] = {}
    if inputs.get("title"):
        updates["title"] = inputs["title"]
    if inputs.get("description"):
        updates["description"] = inputs["description"]
    if inputs.get("state_id"):
        updates["stateId"] = inputs["state_id"]
    if inputs.get("priority") is not None:
        updates["priority"] = inputs["priority"]
    if inputs.get("assignee_id"):
        updates["assigneeId"] = inputs["assignee_id"]

    result = await linear.update_issue(inputs["issue_id"], updates)
    issue = result.get("issue", {})

    return {
        "issue": issue,
        "identifier": issue.get("identifier"),
        "url": issue.get("url"),
    }
