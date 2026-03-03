export default async ({ inputs, settings, config }) => {
  const urlString = inputs.url;

  if (typeof urlString !== "string" || urlString === "") {
    return {
      protocol: "",
      host: "",
      hostname: "",
      port: "",
      pathname: "",
      search: "",
      query: {},
      hash: "",
      origin: "",
    };
  }

  try {
    const url = new URL(urlString);

    // Parse query parameters into object
    const query = {};
    url.searchParams.forEach((value, key) => {
      if (key in query) {
        // Handle multiple values for same key
        if (Array.isArray(query[key])) {
          query[key].push(value);
        } else {
          query[key] = [query[key], value];
        }
      } else {
        query[key] = value;
      }
    });

    return {
      protocol: url.protocol,
      host: url.host,
      hostname: url.hostname,
      port: url.port,
      pathname: url.pathname,
      search: url.search,
      query,
      hash: url.hash,
      origin: url.origin,
    };
  } catch (e) {
    // Return empty values for invalid URLs
    return {
      protocol: "",
      host: "",
      hostname: "",
      port: "",
      pathname: "",
      search: "",
      query: {},
      hash: "",
      origin: "",
    };
  }
};
