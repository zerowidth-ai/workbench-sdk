export default async ({ inputs, settings, config }) => {
  const json = inputs.json;
  const indent = inputs.indent ?? 2;

  if (json === null || json === undefined) {
    return { yaml: "null" };
  }

  const toYaml = (value, depth = 0) => {
    const spaces = " ".repeat(indent * depth);
    const childSpaces = " ".repeat(indent * (depth + 1));

    if (value === null) return "null";
    if (value === undefined) return "null";
    if (typeof value === "boolean") return value.toString();
    if (typeof value === "number") return value.toString();

    if (typeof value === "string") {
      // Check if string needs quoting
      if (
        value === "" ||
        value.includes("\n") ||
        value.includes(":") ||
        value.includes("#") ||
        value.startsWith(" ") ||
        value.endsWith(" ") ||
        value === "true" ||
        value === "false" ||
        value === "null" ||
        /^[\d.-]+$/.test(value)
      ) {
        // Use double quotes and escape
        return JSON.stringify(value);
      }
      return value;
    }

    if (Array.isArray(value)) {
      if (value.length === 0) return "[]";

      const items = value.map((item) => {
        const itemYaml = toYaml(item, depth);
        if (typeof item === "object" && item !== null && !Array.isArray(item) && Object.keys(item).length > 0) {
          // Object in array - put first key on same line as dash
          const lines = itemYaml.split("\n");
          const rest = lines.slice(1);
          if (rest.length > 0) {
            return `- ${lines[0]}\n${rest.join("\n")}`;
          }
          return `- ${lines[0]}`;
        }
        return `- ${itemYaml}`;
      });

      return items.join("\n");
    }

    if (typeof value === "object") {
      const keys = Object.keys(value);
      if (keys.length === 0) return "{}";

      const pairs = keys.map((key) => {
        const val = value[key];

        // Check if key needs quoting
        const safeKey = /^[\w-]+$/.test(key) ? key : JSON.stringify(key);

        if (typeof val === "object" && val !== null && !Array.isArray(val) && Object.keys(val).length > 0) {
          const valYaml = toYaml(val, depth + 1);
          return `${safeKey}:\n${childSpaces}${valYaml.split("\n").join("\n" + childSpaces)}`;
        }
        if (Array.isArray(val) && val.length > 0) {
          const valYaml = toYaml(val, depth + 1);
          return `${safeKey}:\n${childSpaces}${valYaml.split("\n").join("\n" + childSpaces)}`;
        }
        const valYaml = toYaml(val, depth + 1);
        return `${safeKey}: ${valYaml}`;
      });

      return pairs.join("\n");
    }

    return String(value);
  };

  const yaml = toYaml(json);

  return { yaml };
};
