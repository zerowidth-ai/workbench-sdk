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
  const parentType = inputs.parent_type;
  const parentId = inputs.parent_id;
  const properties = inputs.properties;

  if (!parentType) {
    throw new Error("parent_type is required ('database_id' or 'page_id')");
  }
  if (parentType !== "database_id" && parentType !== "page_id") {
    throw new Error("parent_type must be 'database_id' or 'page_id'");
  }
  if (!parentId) {
    throw new Error("parent_id is required");
  }
  if (!properties) {
    throw new Error("properties is required");
  }

  // Build parent object
  const parent = { [parentType]: parentId };

  // Create the page
  const page = await notion.createPage(parent, properties, {
    children: inputs.children,
    icon: inputs.icon,
    cover: inputs.cover,
  });

  return {
    page: page,
    id: page.id,
    url: page.url,
  };
};
