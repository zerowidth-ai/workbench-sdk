export default async ({ inputs, settings, config }) => {
  const github = config.integrations?.github;
  if (!github) {
    throw new Error("GitHub integration not configured. Add your GitHub PAT to config.keys.github");
  }

  if (!inputs.owner) throw new Error("owner is required");
  if (!inputs.repo) throw new Error("repo is required");
  if (!inputs.title) throw new Error("title is required");

  const issue = await github.createIssue(inputs.owner, inputs.repo, inputs.title, {
    body: inputs.body || undefined,
    labels: inputs.labels || undefined,
    assignees: inputs.assignees || undefined,
  });

  return {
    issue,
    number: issue.number,
    url: issue.html_url,
  };
};
