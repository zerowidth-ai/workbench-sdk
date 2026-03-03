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
  const pageId = inputs.page_id;
  if (!pageId) {
    throw new Error("page_id is required");
  }

  // Default to archiving if not specified
  const archived = inputs.archived !== undefined ? inputs.archived : true;

  // Archive or restore the page
  const page = await notion.archivePage(pageId, archived);

  return {
    page: page,
    id: page.id,
    archived: page.archived || false,
  };
};
