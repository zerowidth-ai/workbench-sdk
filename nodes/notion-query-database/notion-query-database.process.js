export default async ({ inputs, settings, config }) => {
  // Get Notion integration
  const integrations = config.integrations || {};
  const notion = integrations.notion;

  if (!notion) {
    throw new Error(
      "Notion integration not configured. Add your Notion API key to config.keys.notion"
    );
  }

  // Get required inputs
  const databaseId = inputs.database_id;
  if (!databaseId) {
    throw new Error("database_id is required");
  }

  // Query the database
  const response = await notion.queryDatabase(databaseId, {
    filter: inputs.filter,
    sorts: inputs.sorts,
    startCursor: inputs.start_cursor,
    pageSize: inputs.page_size,
  });

  return {
    results: response.results || [],
    has_more: response.has_more || false,
    next_cursor: response.next_cursor || null,
  };
};
