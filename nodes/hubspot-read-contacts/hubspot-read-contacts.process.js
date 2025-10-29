export default async ({inputs, settings, config, nodeConfig}) => {
  // Get HubSpot integration
  const hubspot = config.integrations?.hubspot;
  if (!hubspot) {
    throw new Error("HubSpot integration not found");
  }

  // Build query parameters
  const params = {};

  // Add limit if provided (default is handled by API, but we can be explicit)
  if (inputs.limit !== null && inputs.limit !== undefined) {
    params.limit = inputs.limit;
  }

  // Add after (paging cursor) if provided
  if (inputs.after) {
    params.after = inputs.after;
  }

  // Handle properties - convert array to comma-separated string if needed
  // Default value is set in config, so this will always have a value
  if (inputs.properties) {
    if (Array.isArray(inputs.properties)) {
      params.properties = inputs.properties.join(',');
    } else if (typeof inputs.properties === 'string') {
      params.properties = inputs.properties;
    }
  }

  // Handle associations - convert array to comma-separated string if needed
  if (inputs.associations) {
    if (Array.isArray(inputs.associations)) {
      params.associations = inputs.associations.join(',');
    } else if (typeof inputs.associations === 'string') {
      params.associations = inputs.associations;
    }
  }

  // Make API request
  const response = await hubspot.get('/crm/v3/objects/contacts', params);

  // Extract results and paging information
  const contacts = response.results || [];
  const paging = response.paging || {};

  // Return formatted output
  return {
    contacts: contacts,
    paging_next_after: paging.next?.after || null,
    paging_next_link: paging.next?.link || null,
    paging_prev_before: paging.prev?.before || null,
    paging_prev_link: paging.prev?.link || null
  };
};

