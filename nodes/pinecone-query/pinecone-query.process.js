export default async ({ inputs, settings, config }) => {
  const pinecone = config.integrations?.pinecone;
  if (!pinecone) {
    throw new Error("Pinecone integration not configured. Add your Pinecone config to config.keys.pinecone ({api_key, host})");
  }

  if (!inputs.vector) throw new Error("vector is required");
  if (!Array.isArray(inputs.vector)) throw new Error("vector must be an array of numbers");

  const result = await pinecone.query(inputs.vector, {
    top_k: inputs.top_k ?? 10,
    namespace: inputs.namespace || undefined,
    filter: inputs.filter || undefined,
    include_metadata: inputs.include_metadata !== false,
    include_values: inputs.include_values || false,
  });

  return {
    matches: result.matches || [],
    namespace: result.namespace || "",
  };
};
