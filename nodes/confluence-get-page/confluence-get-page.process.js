export default async ({ inputs, settings, config }) => {
  const confluence = config.integrations?.confluence;
  if (!confluence) {
    throw new Error("Confluence integration not configured. Add your Confluence config to config.keys.confluence ({email, api_token, domain})");
  }

  if (!inputs.page_id) throw new Error("page_id is required");

  const page = await confluence.getPage(inputs.page_id, {
    bodyFormat: inputs.body_format || 'storage',
  });

  // Extract body from the format-specific key
  const format = inputs.body_format || 'storage';
  const bodyContent = page.body?.[format]?.value || page.body?.[format]?.representation || '';

  return {
    page,
    title: page.title || '',
    body: bodyContent,
  };
};
