export default async ({ inputs, settings, config }) => {
  const linear = config.integrations?.linear;
  if (!linear) {
    throw new Error("Linear integration not configured. Add your Linear API key to config.keys.linear");
  }

  const result = await linear.listIssues({
    first: inputs.first ?? 25,
    after: inputs.after || undefined,
    filter: inputs.filter || undefined,
  });

  const nodes = result.nodes || [];
  const pageInfo = result.pageInfo || {};

  return {
    issues: nodes,
    count: nodes.length,
    has_more: pageInfo.hasNextPage || false,
    end_cursor: pageInfo.endCursor || null,
  };
};
