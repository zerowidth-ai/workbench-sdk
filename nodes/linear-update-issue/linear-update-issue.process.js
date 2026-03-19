export default async ({ inputs, settings, config }) => {
  const linear = config.integrations?.linear;
  if (!linear) {
    throw new Error("Linear integration not configured. Add your Linear API key to config.keys.linear");
  }

  if (!inputs.issue_id) throw new Error("issue_id is required");

  const updates = {};
  if (inputs.title) updates.title = inputs.title;
  if (inputs.description) updates.description = inputs.description;
  if (inputs.state_id) updates.stateId = inputs.state_id;
  if (inputs.priority !== undefined && inputs.priority !== null) updates.priority = inputs.priority;
  if (inputs.assignee_id) updates.assigneeId = inputs.assignee_id;

  const result = await linear.updateIssue(inputs.issue_id, updates);
  const issue = result.issue || {};

  return {
    issue,
    identifier: issue.identifier,
    url: issue.url,
  };
};
