export default async ({ inputs, settings, config }) => {
  let html = inputs.html;
  const preserveLineBreaks = inputs.preserve_line_breaks ?? true;
  const decodeEntities = inputs.decode_entities ?? true;

  if (typeof html !== "string") {
    return { text: "" };
  }

  // Convert block-level tags to newlines if preserving line breaks
  if (preserveLineBreaks) {
    html = html.replace(/<br\s*\/?>/gi, "\n");
    html = html.replace(/<\/(p|div|h[1-6]|li|tr)>/gi, "\n");
    html = html.replace(/<(p|div|h[1-6]|li|tr)[^>]*>/gi, "");
  }

  // Remove all HTML tags
  let text = html.replace(/<[^>]*>/g, "");

  // Decode HTML entities if requested
  if (decodeEntities) {
    const entities = {
      "&amp;": "&",
      "&lt;": "<",
      "&gt;": ">",
      "&quot;": '"',
      "&#39;": "'",
      "&apos;": "'",
      "&nbsp;": " ",
      "&copy;": "\u00A9",
      "&reg;": "\u00AE",
      "&trade;": "\u2122",
      "&mdash;": "\u2014",
      "&ndash;": "\u2013",
      "&hellip;": "\u2026",
      "&ldquo;": "\u201C",
      "&rdquo;": "\u201D",
      "&lsquo;": "\u2018",
      "&rsquo;": "\u2019",
    };
    for (const [entity, char] of Object.entries(entities)) {
      text = text.split(entity).join(char);
    }
    // Handle numeric entities
    text = text.replace(/&#(\d+);/g, (_, code) =>
      String.fromCharCode(parseInt(code, 10))
    );
    text = text.replace(/&#x([0-9a-fA-F]+);/g, (_, code) =>
      String.fromCharCode(parseInt(code, 16))
    );
  }

  // Normalize whitespace
  text = text.replace(/[ \t]+/g, " ");
  text = text.replace(/\n[ \t]+/g, "\n");
  text = text.replace(/[ \t]+\n/g, "\n");
  text = text.replace(/\n{3,}/g, "\n\n");
  text = text.trim();

  return { text };
};
