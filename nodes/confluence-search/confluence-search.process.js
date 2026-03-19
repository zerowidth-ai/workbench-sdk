export default async ({ inputs, settings, config }) => {
  const confluence = config.integrations?.confluence;
  if (!confluence) {
    throw new Error("Confluence integration not configured. Add your Confluence config to config.keys.confluence ({email, api_token, domain})");
  }

  if (!inputs.cql) throw new Error("cql is required");

  const result = await confluence.search(inputs.cql, {
    limit: inputs.limit ?? 25,
    start: inputs.start ?? 0,
  });

  const results = result.results || [];

  return {
    results,
    total_size: result.totalSize ?? 0,
    count: results.length,
  };
};
