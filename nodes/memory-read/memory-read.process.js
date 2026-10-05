export default async ({ inputs, config }) => {
  const memory = config.integrations?.memory;
  if (!memory) throw new Error("No memory is available. Pass config.memory to the engine.");
  const path = memory.normalize(inputs.path);
  const content = await memory.read(path);
  if (content === null) throw new Error(`${path} doesn't exist yet.`);
  return { path, content };
};
