export default async ({ inputs, settings, config }) => {
  const pinecone = config.integrations?.pinecone;
  if (!pinecone) {
    throw new Error("Pinecone integration not configured. Add your Pinecone config to config.keys.pinecone ({api_key, host})");
  }

  if (!inputs.vectors) throw new Error("vectors is required");
  if (!Array.isArray(inputs.vectors)) throw new Error("vectors must be an array");

  const result = await pinecone.upsert(inputs.vectors, inputs.namespace || undefined);

  return {
    upserted_count: result.upsertedCount ?? inputs.vectors.length,
  };
};
