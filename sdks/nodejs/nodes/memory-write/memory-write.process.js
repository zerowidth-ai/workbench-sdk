export default async ({ inputs, config }) => {
  const memory = config.integrations?.memory;
  if (!memory) throw new Error("No memory is available. Pass config.memory to the engine.");
  const path = memory.normalize(inputs.path);
  const { status } = await memory.write(path, String(inputs.content ?? ""), { tool: "write" });
  return { path, saved: status === "held" ? "waiting for approval" : "saved" };
};
