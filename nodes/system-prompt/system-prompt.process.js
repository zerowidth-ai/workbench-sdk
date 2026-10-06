/**
 * Process function for the System Prompt node.
 * Outputs a message object, containing the prompt text and system role and text
 */
/**
 * Render a variable value for injection into prompt text.
 * Strings pass through untouched; everything else is JSON encoded so that
 * nested objects and arrays read as data instead of "[object Object]".
 */
const renderVariable = (value) => {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    // Circular structures (or anything else JSON can't encode) fall back to
    // the default coercion rather than failing the whole prompt.
    return String(value);
  }
};

export default async ({inputs, settings, config}) => {
  // Initialize variables array if not provided
  if(!inputs.variables) {
    inputs.variables = [];
  }

  // A single connection can deliver an array of key-value objects, so flatten
  // one level before looking keys up.
  const variables = (Array.isArray(inputs.variables) ? inputs.variables : [inputs.variables])
    .flatMap(entry => Array.isArray(entry) ? entry : [entry])
    .filter(entry => entry !== null && typeof entry === "object");

  // Get the base content from settings
  let baseContent = settings.content || "";

  // Handle chain input if provided
  let chainedContent = "";
  if (inputs.chain) {
    if (typeof inputs.chain === "string") {
      chainedContent = inputs.chain;
    } else if (typeof inputs.chain === "object" && inputs.chain.content) {
      // Handle message object format
      if (Array.isArray(inputs.chain.content)) {
        // Extract text content from array format
        chainedContent = inputs.chain.content
          .filter(item => item.type === "text")
          .map(item => item.text)
          .join("\n");
      } else if (typeof inputs.chain.content === "string") {
        chainedContent = inputs.chain.content;
      }
    }
  }

  // Combine chained content with base content
  let fullContent = chainedContent ? `${chainedContent}\n\n${baseContent}` : baseContent;

  const fill = (text) =>
    text.replace(/\{\{(.*?)\}\}/g, (match, p1) => {
      // look for a variable with the key p1
      let variable = variables.find(variable => Object.keys(variable).find(key => key === p1));
      if(variable) {
        return renderVariable(variable[p1]);
      }
      return match;
    });

  // Values filled in can change from run to run (the time, memory, search
  // results); the text before the first of them doesn't. The message keeps
  // the two as separate blocks and marks the fixed one with
  // `cache_control`, so a model that caches on request can reuse the
  // prompt up to there. The model client removes the mark for models
  // that don't take it.
  let firstFilled = -1;
  for (const m of fullContent.matchAll(/\{\{(.*?)\}\}/g)) {
    if (variables.some(variable => Object.keys(variable).includes(m[1]))) {
      firstFilled = m.index;
      break;
    }
  }

  const CACHE = { type: "ephemeral" };
  let message;
  if (firstFilled < 0) {
    message = {
      role: "system",
      content: [{ type: "text", text: fullContent, ...(fullContent.trim() ? { cache_control: CACHE } : {}) }],
    };
  } else {
    const fixed = fullContent.slice(0, firstFilled);
    const changing = fill(fullContent.slice(firstFilled));
    message = {
      role: "system",
      content: fixed.trim()
        ? [{ type: "text", text: fixed, cache_control: CACHE }, ...(changing ? [{ type: "text", text: changing }] : [])]
        : [{ type: "text", text: changing }],
    };
  }

  // Return the message and string prompt
  return {
    message: message,
    prompt: message.content.map(block => block.text).join("")
  };
}; 