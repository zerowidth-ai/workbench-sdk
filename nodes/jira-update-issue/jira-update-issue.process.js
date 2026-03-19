export default async ({ inputs, settings, config }) => {
  const jira = config.integrations?.jira;
  if (!jira) {
    throw new Error("Jira integration not configured. Add your Jira config to config.keys.jira ({email, api_token, domain})");
  }

  if (!inputs.issue_key) throw new Error("issue_key is required");

  const fields = {};
  if (inputs.summary) fields.summary = inputs.summary;
  if (inputs.description) {
    fields.description = {
      type: 'doc',
      version: 1,
      content: [{
        type: 'paragraph',
        content: [{ type: 'text', text: inputs.description }]
      }]
    };
  }
  if (inputs.priority) fields.priority = { name: inputs.priority };
  if (inputs.labels) fields.labels = inputs.labels;
  if (inputs.assignee_id) fields.assignee = { accountId: inputs.assignee_id };

  await jira.updateIssue(inputs.issue_key, fields);

  return {
    issue_key: inputs.issue_key,
  };
};
