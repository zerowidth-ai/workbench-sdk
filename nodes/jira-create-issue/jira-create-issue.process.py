"""
Jira Create Issue Node - Create a new issue in Jira.
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

    if not inputs.get("project_key"):
        raise Exception("project_key is required")
    if not inputs.get("summary"):
        raise Exception("summary is required")

    issue = await jira.create_issue(
        inputs["project_key"],
        inputs["summary"],
        issue_type=inputs.get("issue_type", "Task"),
        description=inputs.get("description"),
        priority=inputs.get("priority"),
        labels=inputs.get("labels"),
        assignee_id=inputs.get("assignee_id"),
        parent_key=inputs.get("parent_key"),
    )

    return {
        "issue": issue,
        "key": issue.get("key"),
        "id": issue.get("id"),
    }
