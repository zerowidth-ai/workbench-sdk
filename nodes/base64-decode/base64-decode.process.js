export default async ({ inputs, settings, config }) => {
  const encoded = inputs.encoded;

  if (typeof encoded !== "string") {
    return { text: "", success: false, error: "Input must be a string" };
  }

  if (encoded === "") {
    return { text: "", success: true, error: null };
  }

  try {
    const text = Buffer.from(encoded, "base64").toString("utf-8");
    return { text, success: true, error: null };
  } catch (e) {
    return { text: "", success: false, error: e.message };
  }
};
