export default async ({ inputs, settings, config }) => {
  const yaml = inputs.yaml;

  if (typeof yaml !== "string") {
    return { json: null, success: false, error: "Input must be a string" };
  }

  if (yaml.trim() === "") {
    return { json: null, success: true, error: null };
  }

  try {
    const result = parseYaml(yaml);
    return { json: result, success: true, error: null };
  } catch (e) {
    return { json: null, success: false, error: e.message };
  }
};

function parseYaml(yaml) {
  const lines = yaml.split("\n");
  let index = 0;

  function getIndent(line) {
    const match = line.match(/^(\s*)/);
    return match ? match[1].length : 0;
  }

  function parseValue(value) {
    value = value.trim();

    if (value === "" || value === "null" || value === "~") return null;
    if (value === "true") return true;
    if (value === "false") return false;

    // Quoted string
    if ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))) {
      return value.slice(1, -1).replace(/\\n/g, "\n").replace(/\\"/g, '"');
    }

    // Number
    if (/^-?\d+$/.test(value)) return parseInt(value, 10);
    if (/^-?\d+\.\d+$/.test(value)) return parseFloat(value);

    // Empty object/array
    if (value === "{}") return {};
    if (value === "[]") return [];

    return value;
  }

  function parseBlock(minIndent) {
    const result = {};
    let isArray = null;
    const arrayResult = [];

    while (index < lines.length) {
      const line = lines[index];

      // Skip empty lines and comments
      if (line.trim() === "" || line.trim().startsWith("#")) {
        index++;
        continue;
      }

      const indent = getIndent(line);

      // If we've dedented, we're done with this block
      if (indent < minIndent) {
        break;
      }

      const trimmed = line.trim();

      // Array item
      if (trimmed.startsWith("- ")) {
        if (isArray === false) throw new Error("Mixed array and object syntax");
        isArray = true;

        const content = trimmed.slice(2);

        // Check if it's a key-value on same line as dash
        if (content.includes(": ")) {
          const colonPos = content.indexOf(": ");
          const key = content.slice(0, colonPos);
          const value = content.slice(colonPos + 2);

          index++;
          const childIndent = indent + 2;

          // Check if there are more keys at the child indent level
          const obj = { [key]: parseValue(value) };

          while (index < lines.length) {
            const nextLine = lines[index];
            if (nextLine.trim() === "" || nextLine.trim().startsWith("#")) {
              index++;
              continue;
            }
            const nextIndent = getIndent(nextLine);
            if (nextIndent < childIndent || nextLine.trim().startsWith("- ")) {
              break;
            }
            if (nextIndent === childIndent) {
              const nextTrimmed = nextLine.trim();
              if (nextTrimmed.includes(": ")) {
                const nextColonPos = nextTrimmed.indexOf(": ");
                const nextKey = nextTrimmed.slice(0, nextColonPos);
                const nextValue = nextTrimmed.slice(nextColonPos + 2);
                obj[nextKey] = parseValue(nextValue);
                index++;
              } else {
                break;
              }
            } else {
              break;
            }
          }

          arrayResult.push(obj);
        } else {
          index++;
          arrayResult.push(parseValue(content));
        }
        continue;
      }

      // Key-value pair
      if (trimmed.includes(": ")) {
        if (isArray === true) throw new Error("Mixed array and object syntax");
        isArray = false;

        const colonPos = trimmed.indexOf(": ");
        const key = trimmed.slice(0, colonPos);
        const value = trimmed.slice(colonPos + 2);

        index++;

        if (value === "" || value === "|" || value === ">") {
          // Nested block
          const nextIndent = index < lines.length ? getIndent(lines[index]) : indent;
          if (nextIndent > indent && index < lines.length && !lines[index].trim().startsWith("#")) {
            result[key] = parseBlock(nextIndent);
          } else {
            result[key] = null;
          }
        } else {
          result[key] = parseValue(value);
        }
        continue;
      }

      // Key without value (nested object follows)
      if (trimmed.endsWith(":")) {
        if (isArray === true) throw new Error("Mixed array and object syntax");
        isArray = false;

        const key = trimmed.slice(0, -1);
        index++;

        const nextIndent = index < lines.length ? getIndent(lines[index]) : indent;
        if (nextIndent > indent) {
          result[key] = parseBlock(nextIndent);
        } else {
          result[key] = null;
        }
        continue;
      }

      index++;
    }

    return isArray ? arrayResult : result;
  }

  return parseBlock(0);
}
