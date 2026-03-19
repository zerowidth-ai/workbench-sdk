"""
GitHub Create Issue Node - Create a new issue in a GitHub repository.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    github = config.get("integrations", {}).get("github")
    if not github:
        raise Exception("GitHub integration not configured. Add your GitHub PAT to config.keys.github")

    if not inputs.get("owner"):
        raise Exception("owner is required")
    if not inputs.get("repo"):
        raise Exception("repo is required")
    if not inputs.get("title"):
        raise Exception("title is required")

    issue = await github.create_issue(
        inputs["owner"],
        inputs["repo"],
        inputs["title"],
        body=inputs.get("body"),
        labels=inputs.get("labels"),
        assignees=inputs.get("assignees"),
    )

    return {
        "issue": issue,
        "number": issue.get("number"),
        "url": issue.get("html_url"),
    }
