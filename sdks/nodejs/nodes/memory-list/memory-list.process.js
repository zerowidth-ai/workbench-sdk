export default async ({ config }) => {
  const memory = config.integrations?.memory;
  if (!memory) throw new Error("No memory is available. Pass config.memory to the engine.");
  const files = await memory.list();
  return { files: files.map((f) => ({ path: f.path, size: f.size })) };
};
