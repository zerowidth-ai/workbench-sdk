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
  const properties = inputs.properties;

  if (!pageId) {
    throw new Error("page_id is required");
  }
  if (!properties) {
    throw new Error("properties is required");
  }

  // Update the page
  const page = await notion.updatePage(pageId, properties, {
    icon: inputs.icon,
    cover: inputs.cover,
  });

  return {
    page: page,
    id: page.id,
    last_edited_time: page.last_edited_time,
  };
};
