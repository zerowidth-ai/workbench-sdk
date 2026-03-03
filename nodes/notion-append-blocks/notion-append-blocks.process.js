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
  const children = inputs.children;

  if (!blockId) {
    throw new Error("block_id is required");
  }
  if (!children) {
    throw new Error("children is required");
  }
  if (!Array.isArray(children)) {
    throw new Error("children must be an array of block objects");
  }

  // Append blocks
  const response = await notion.appendBlockChildren(blockId, children, {
    after: inputs.after,
  });

  return {
    results: response.results || [],
  };
};
