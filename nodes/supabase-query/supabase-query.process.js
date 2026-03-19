export default async ({ inputs, settings, config }) => {
  const supabase = config.integrations?.supabase;
  if (!supabase) {
    throw new Error("Supabase integration not configured. Add your Supabase config to config.keys.supabase ({url, key})");
  }

  if (!inputs.table) throw new Error("table is required");

  const rows = await supabase.query(inputs.table, {
    select: inputs.select || "*",
    filter: inputs.filters ?? undefined,
    order: inputs.order || undefined,
    limit: inputs.limit ?? undefined,
    offset: inputs.offset ?? undefined,
  });

  return {
    rows: Array.isArray(rows) ? rows : [],
    count: Array.isArray(rows) ? rows.length : 0,
  };
};
