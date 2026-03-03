export default async ({ inputs }) => {
  const tools = inputs.tools || [];
  const include = inputs.include || [];

  if (include.length === 0) {
    return { tools: [] };
  }

  const includeSet = new Set(include);
  const filtered = tools.filter(t => includeSet.has(t.name));

  return { tools: filtered };
};
