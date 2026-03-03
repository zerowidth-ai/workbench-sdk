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

  // Get the page
  const page = await notion.getPage(pageId);

  return {
    page: page,
    id: page.id,
    properties: page.properties || {},
    created_time: page.created_time,
    last_edited_time: page.last_edited_time,
    archived: page.archived || false,
  };
};
