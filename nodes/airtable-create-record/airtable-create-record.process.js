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
  const fields = inputs.fields;

  if (!baseId) {
    throw new Error("base_id is required");
  }
  if (!tableName) {
    throw new Error("table_name is required");
  }
  if (!fields) {
    throw new Error("fields is required");
  }
  if (typeof fields !== "object" || Array.isArray(fields)) {
    throw new Error("fields must be an object");
  }

  // Get optional inputs
  const typecast = inputs.typecast || false;

  // Make API request
  const record = await airtable.createRecord(baseId, tableName, fields, {
    typecast,
  });

  return {
    record,
    id: record.id,
    fields: record.fields || {},
    created_time: record.createdTime,
  };
};
