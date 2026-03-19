export default async ({ inputs, settings, config }) => {
  const jira = config.integrations?.jira;
  if (!jira) {
    throw new Error("Jira integration not configured. Add your Jira config to config.keys.jira ({email, api_token, domain})");
  }

  if (!inputs.jql) throw new Error("jql is required");

  const result = await jira.listIssues(inputs.jql, {
    maxResults: inputs.max_results ?? 25,
    startAt: inputs.start_at ?? 0,
  });

  return {
    issues: result.issues || [],
    total: result.total ?? 0,
    count: result.issues ? result.issues.length : 0,
  };
};
