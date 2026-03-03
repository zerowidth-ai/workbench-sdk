export default async ({ inputs, settings, config }) => {
  let text = inputs.text;
  const collapseSpaces = inputs.collapse_spaces ?? true;
  const collapseNewlines = inputs.collapse_newlines ?? true;
  const trim = inputs.trim ?? true;
  const trimLines = inputs.trim_lines ?? false;

  if (typeof text !== "string") {
    return { text: "" };
  }

  // Trim each line if requested
  if (trimLines) {
    text = text
      .split("\n")
      .map((line) => line.trim())
      .join("\n");
  }

  // Collapse multiple newlines into single newline
  if (collapseNewlines) {
    text = text.replace(/\n{2,}/g, "\n");
  }

  // Collapse multiple spaces into single space
  if (collapseSpaces) {
    text = text.replace(/[ \t]{2,}/g, " ");
  }

  // Trim leading and trailing whitespace
  if (trim) {
    text = text.trim();
  }

  return { text };
};
