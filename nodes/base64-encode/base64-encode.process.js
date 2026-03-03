export default async ({ inputs, settings, config }) => {
  const text = inputs.text;

  if (typeof text !== "string") {
    return { encoded: "" };
  }

  const encoded = Buffer.from(text, "utf-8").toString("base64");

  return { encoded };
};
