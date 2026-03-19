export default async ({ inputs, settings, config }) => {
  const linear = config.integrations?.linear;
  if (!linear) {
    throw new Error("Linear integration not configured. Add your Linear API key to config.keys.linear");
  }

  if (!inputs.team_id) throw new Error("team_id is required");
  if (!inputs.title) throw new Error("title is required");

  const result = await linear.createIssue(inputs.team_id, inputs.title, {
    description: inputs.description || undefined,
    priority: inputs.priority !== undefined ? inputs.priority : undefined,
    assigneeId: inputs.assignee_id || undefined,
    labelIds: inputs.label_ids || undefined,
  });

  const issue = result.issue || {};

  return {
    issue,
    identifier: issue.identifier,
    url: issue.url,
  };
};
