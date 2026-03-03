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
  const blockId = inputs.block_id;
  if (!blockId) {
    throw new Error("block_id is required");
  }

  // Get block children
  const response = await notion.getBlockChildren(blockId, {
    startCursor: inputs.start_cursor,
    pageSize: inputs.page_size,
  });

  return {
    results: response.results || [],
    has_more: response.has_more || false,
    next_cursor: response.next_cursor || null,
  };
};
