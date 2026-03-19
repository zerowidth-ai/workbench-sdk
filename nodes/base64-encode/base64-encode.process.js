export default async ({ inputs, settings, config, nodeConfig }) => {
  const text = inputs.text;

  if (typeof text !== "string") {
    throw new Error("base64-encode: input 'text' must be a string");
  }

  const encoded = Buffer.from(text, "utf-8").toString("base64");

  return { encoded };
};
