export default async ({ inputs, settings, config }) => {
  const xml = inputs.xml;
  const removeRoot = inputs.remove_root ?? false;

  if (typeof xml !== "string") {
    return { json: null, success: false, error: "Input must be a string" };
  }

  if (xml.trim() === "") {
    return { json: null, success: true, error: null };
  }

  try {
    let result = parseXml(xml.trim());

    if (removeRoot && result && typeof result === "object") {
      const keys = Object.keys(result);
      if (keys.length === 1) {
        result = result[keys[0]];
      }
    }

    return { json: result, success: true, error: null };
  } catch (e) {
    return { json: null, success: false, error: e.message };
  }
};

function parseXml(xml) {
  let index = 0;

  function skipWhitespace() {
    while (index < xml.length && /\s/.test(xml[index])) {
      index++;
    }
  }

  function parseText() {
    let text = "";
    while (index < xml.length && xml[index] !== "<") {
      text += xml[index];
      index++;
    }
    return decodeEntities(text.trim());
  }

  function decodeEntities(text) {
    return text
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&")
      .replace(/&quot;/g, '"')
      .replace(/&apos;/g, "'");
  }

  function parseTagName() {
    let name = "";
    while (index < xml.length && /[a-zA-Z0-9_-]/.test(xml[index])) {
      name += xml[index];
      index++;
    }
    return name;
  }

  function parseElement() {
    skipWhitespace();

    if (index >= xml.length || xml[index] !== "<") {
      return parseText();
    }

    index++; // skip <

    // Check for closing tag
    if (xml[index] === "/") {
      return null;
    }

    const tagName = parseTagName();
    if (!tagName) {
      throw new Error("Invalid XML: expected tag name");
    }

    // Skip attributes (we don't parse them)
    while (index < xml.length && xml[index] !== ">" && xml[index] !== "/") {
      index++;
    }

    // Self-closing tag
    if (xml[index] === "/") {
      index += 2; // skip />
      return { [tagName]: null };
    }

    index++; // skip >

    // Parse children
    const children = [];
    let textContent = "";

    while (index < xml.length) {
      skipWhitespace();

      if (index >= xml.length) break;

      // Check for closing tag
      if (xml[index] === "<" && xml[index + 1] === "/") {
        index += 2;
        const closingTag = parseTagName();
        if (closingTag !== tagName) {
          throw new Error(`Mismatched tags: ${tagName} and ${closingTag}`);
        }
        while (index < xml.length && xml[index] !== ">") index++;
        index++; // skip >
        break;
      }

      // Check for child element
      if (xml[index] === "<") {
        const child = parseElement();
        if (child !== null) {
          children.push(child);
        }
      } else {
        // Text content
        textContent += parseText();
      }
    }

    // Determine result structure
    if (children.length === 0) {
      // Text-only content
      const text = textContent.trim();
      if (text === "") return { [tagName]: null };
      if (text === "true") return { [tagName]: true };
      if (text === "false") return { [tagName]: false };
      if (/^-?\d+$/.test(text)) return { [tagName]: parseInt(text, 10) };
      if (/^-?\d+\.\d+$/.test(text)) return { [tagName]: parseFloat(text) };
      return { [tagName]: text };
    }

    // Merge children
    const result = {};

    for (const child of children) {
      for (const [key, value] of Object.entries(child)) {
        if (key in result) {
          // Convert to array
          if (!Array.isArray(result[key])) {
            result[key] = [result[key]];
          }
          result[key].push(value);
        } else {
          result[key] = value;
        }
      }
    }

    return { [tagName]: result };
  }

  return parseElement();
}
