export default async ({inputs, settings, config, nodeConfig}) => {
  // Get HubSpot integration
  const hubspot = config.integrations?.hubspot;
  if (!hubspot) {
    throw new Error("HubSpot integration not found");
  }

  // Build request body
  const body = {
    query: inputs.query
  };

  // Add properties - convert array to array if needed (API expects array)
  if (inputs.properties) {
    if (Array.isArray(inputs.properties)) {
      body.properties = inputs.properties;
    } else if (typeof inputs.properties === 'string') {
      // Split comma-separated string into array
      body.properties = inputs.properties.split(',').map(p => p.trim()).filter(p => p.length > 0);
    }
  }

  // Add limit if provided
  if (inputs.limit !== null && inputs.limit !== undefined) {
    body.limit = Math.min(inputs.limit, 200); // Cap at 200 as per API
  }

  // Add after (paging cursor) if provided
  if (inputs.after) {
    body.after = inputs.after;
  }

  // Add sorts - convert string to array if needed
  if (inputs.sorts) {
    if (Array.isArray(inputs.sorts)) {
      body.sorts = inputs.sorts;
    } else if (typeof inputs.sorts === 'string') {
      // Split comma-separated string into array
      body.sorts = inputs.sorts.split(',').map(s => s.trim()).filter(s => s.length > 0);
    }
  }

  // Add filterGroups if provided (complex object, pass as-is)
  if (inputs.filter_groups && Array.isArray(inputs.filter_groups)) {
    body.filterGroups = inputs.filter_groups;
  }

  // Make API request (POST)
  const response = await hubspot.post('/crm/v3/objects/contacts/search', body);

  // Extract results and paging information
  const contacts = response.results || [];
  const total = response.total || 0;
  const paging = response.paging || {};

  // Return formatted output
  return {
    contacts: contacts,
    total: total,
    paging_next_after: paging.next?.after || null,
    paging_next_link: paging.next?.link || null,
    paging_prev_before: paging.prev?.before || null,
    paging_prev_link: paging.prev?.link || null
  };
};






