export default async ({ inputs, config }) => {
  const memory = config.integrations?.memory;
  if (!memory) throw new Error("No memory is available. Pass config.memory to the engine.");
  const path = memory.normalize(inputs.path);
  const current = await memory.read(path);
  if (current === null) throw new Error(`${path} doesn't exist yet. Write it to create it.`);

  const find = String(inputs.find ?? "");
  const hits = find ? current.split(find).length - 1 : 0;
  if (hits === 0) throw new Error(`That text isn't in ${path}.`);
  if (hits > 1) throw new Error(`That text appears ${hits} times in ${path}; include more of the line.`);

  // A function replacement keeps `$&`-style patterns in the new text literal.
  const next = current.replace(find, () => String(inputs.replace ?? ""));
  const { status } = await memory.write(path, next, { tool: "edit" });
  return { path, saved: status === "held" ? "waiting for approval" : "saved" };
};
