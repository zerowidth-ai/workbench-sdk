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
  const recordId = inputs.record_id;

  if (!baseId) {
    throw new Error("base_id is required");
  }
  if (!tableName) {
    throw new Error("table_name is required");
  }
  if (!recordId) {
    throw new Error("record_id is required");
  }

  // Make API request
  const record = await airtable.getRecord(baseId, tableName, recordId);

  return {
    record,
    id: record.id,
    fields: record.fields || {},
    created_time: record.createdTime,
  };
};
