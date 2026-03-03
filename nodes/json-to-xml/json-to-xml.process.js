export default async ({ inputs, settings, config }) => {
  const json = inputs.json;
  const rootElement = inputs.root_element ?? "root";
  const pretty = inputs.pretty ?? true;
  const indent = inputs.indent ?? 2;

  const escapeXml = (str) => {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  };

  const toXml = (value, tagName, depth = 0) => {
    const spaces = pretty ? " ".repeat(indent * depth) : "";
    const newline = pretty ? "\n" : "";

    if (value === null || value === undefined) {
      return `${spaces}<${tagName}></${tagName}>`;
    }

    if (typeof value === "boolean" || typeof value === "number") {
      return `${spaces}<${tagName}>${value}</${tagName}>`;
    }

    if (typeof value === "string") {
      return `${spaces}<${tagName}>${escapeXml(value)}</${tagName}>`;
    }

    if (Array.isArray(value)) {
      // For arrays, use singular form of tag name for items
      const itemTag = tagName.endsWith("s") ? tagName.slice(0, -1) : "item";
      const items = value.map((item) => toXml(item, itemTag, depth + 1)).join(newline);
      return `${spaces}<${tagName}>${newline}${items}${newline}${spaces}</${tagName}>`;
    }

    if (typeof value === "object") {
      const keys = Object.keys(value);
      if (keys.length === 0) {
        return `${spaces}<${tagName}></${tagName}>`;
      }

      const children = keys.map((key) => {
        // Sanitize key to be valid XML tag name
        const safeKey = key.replace(/[^a-zA-Z0-9_-]/g, "_").replace(/^(\d)/, "_$1");
        return toXml(value[key], safeKey, depth + 1);
      }).join(newline);

      return `${spaces}<${tagName}>${newline}${children}${newline}${spaces}</${tagName}>`;
    }

    return `${spaces}<${tagName}>${escapeXml(String(value))}</${tagName}>`;
  };

  const xml = toXml(json, rootElement, 0);

  return { xml };
};
