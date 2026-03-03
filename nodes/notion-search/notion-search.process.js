export default async ({ inputs, settings, config }) => {
  // Get Notion integration
  const integrations = config.integrations || {};
  const notion = integrations.notion;

  if (!notion) {
    throw new Error(
      "Notion integration not configured. Add your Notion API key to config.keys.notion"
    );
  }

  // Build filter if filter_type is specified
  let filter = null;
  if (inputs.filter_type) {
    filter = { value: inputs.filter_type, property: "object" };
  }

  // Build sort if specified
  let sort = null;
  if (inputs.sort_direction || inputs.sort_timestamp) {
    sort = {
      direction: inputs.sort_direction || "descending",
      timestamp: inputs.sort_timestamp || "last_edited_time",
    };
  }

  // Search
  const response = await notion.search({
    query: inputs.query,
    filter: filter,
    sort: sort,
    startCursor: inputs.start_cursor,
    pageSize: inputs.page_size,
  });

  return {
    results: response.results || [],
    has_more: response.has_more || false,
    next_cursor: response.next_cursor || null,
  };
};
