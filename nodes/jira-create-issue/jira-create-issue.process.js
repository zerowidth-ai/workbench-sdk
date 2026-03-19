export default async ({ inputs, settings, config }) => {
  const jira = config.integrations?.jira;
  if (!jira) {
    throw new Error("Jira integration not configured. Add your Jira config to config.keys.jira ({email, api_token, domain})");
  }

  if (!inputs.project_key) throw new Error("project_key is required");
  if (!inputs.summary) throw new Error("summary is required");

  const issue = await jira.createIssue(inputs.project_key, inputs.summary, {
    issueType: inputs.issue_type || "Task",
    description: inputs.description || undefined,
    priority: inputs.priority || undefined,
    labels: inputs.labels || undefined,
    assigneeId: inputs.assignee_id || undefined,
    parentKey: inputs.parent_key || undefined,
  });

  return {
    issue,
    key: issue.key,
    id: issue.id,
  };
};
