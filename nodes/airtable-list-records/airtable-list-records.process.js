export default async ({ inputs, settings, config }) => {
  // Get Airtable integration
  const integrations = config.integrations || {};
  const airtable = integrations.airtable;

  if (!airtable) {
    throw new Error(
      "Airtable integration not configured. Add your Airtable API key to config.keys.airtable"
    );
  }

  // Get required inputs
  const baseId = inputs.base_id;
  const tableName = inputs.table_name;

  if (!baseId) {
    throw new Error("base_id is required");
  }
  if (!tableName) {
    throw new Error("table_name is required");
  }

  // Build optional params
  const params = {};
  if (inputs.filter_formula) {
    params.filterFormula = inputs.filter_formula;
  }
  if (inputs.sort_field) {
    params.sortField = inputs.sort_field;
    params.sortDirection = inputs.sort_direction || "asc";
  }
  if (inputs.max_records) {
    params.maxRecords = inputs.max_records;
  }
  if (inputs.page_size) {
    params.pageSize = inputs.page_size;
  }
  if (inputs.offset) {
    params.offset = inputs.offset;
  }
  if (inputs.view) {
    params.view = inputs.view;
  }

  // Make API request
  const response = await airtable.listRecords(baseId, tableName, params);

  return {
    records: response.records || [],
    offset: response.offset || null,
  };
};
