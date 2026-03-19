"""
Jira Update Issue Node - Update an existing Jira issue.
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

    if not inputs.get("issue_key"):
        raise Exception("issue_key is required")

    fields: dict[str, Any] = {}
    if inputs.get("summary"):
        fields["summary"] = inputs["summary"]
    if inputs.get("description"):
        fields["description"] = {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": inputs["description"]}]}],
        }
    if inputs.get("priority"):
        fields["priority"] = {"name": inputs["priority"]}
    if inputs.get("labels"):
        fields["labels"] = inputs["labels"]
    if inputs.get("assignee_id"):
        fields["assignee"] = {"accountId": inputs["assignee_id"]}

    await jira.update_issue(inputs["issue_key"], fields)

    return {
        "issue_key": inputs["issue_key"],
    }
