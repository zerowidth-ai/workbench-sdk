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

/**
 * A token's key and its fallback: `name`, or `name:"Unknown Name"` for the
 * text to use when `name` is missing or empty. Inside the quotes, `\"` is a
 * quote and `\\` a backslash. Spaces around the parts are allowed. Null when
 * the token isn't in either form.
 */
const TOKEN = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*"((?:[^"\\]|\\.)*)")?\s*$/;
const parseToken = (inner) => {
  const m = TOKEN.exec(inner);
  if (!m) return null;
  return {
    key: m[1],
    fallback: m[2] === undefined ? undefined : m[2].replace(/\\(.)/g, "$1"),
  };
};

const isEmpty = (value) =>
  value === null || value === undefined || (typeof value === "string" && value.trim() === "");

/**
 * The text a `{{…}}` token becomes, or null to leave it as written: a
 * variable's value, else the token's fallback when the value is missing or
 * empty. A token naming nothing, with no fallback, stays in the text.
 */
const resolveToken = (variables, inner) => {
  // An exact key first, so keys that aren't plain names keep working.
  const exact = variables.find((v) => Object.keys(v).includes(inner));
  if (exact) return renderVariable(exact[inner]);
  const token = parseToken(inner);
  if (!token) return null;
  const found = variables.find((v) => Object.keys(v).includes(token.key));
  const value = found ? found[token.key] : undefined;
  if (!isEmpty(value)) return renderVariable(value);
  if (token.fallback !== undefined) return token.fallback;
  return found ? renderVariable(value) : null;
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
    text.replace(/\{\{(.*?)\}\}/g, (match, p1) => resolveToken(variables, p1) ?? match);

  // Values filled in can change from run to run (the time, memory, search
  // results); the text before the first of them doesn't. The block records
  // that length as `cache_prefix_length`, so the model client can cache
  // the prompt up to there for a model that caches on request. The client
  // removes the hint before any model sees it.
  let firstFilled = -1;
  for (const m of fullContent.matchAll(/\{\{(.*?)\}\}/g)) {
    // A fallback is filled in too, so it ends the fixed part as a value does.
    if (resolveToken(variables, m[1]) !== null) {
      firstFilled = m.index;
      break;
    }
  }

  const text = firstFilled < 0 ? fullContent : fullContent.slice(0, firstFilled) + fill(fullContent.slice(firstFilled));
  const prefix = firstFilled < 0 ? text.length : firstFilled;
  const message = {
    role: "system",
    content: [{ type: "text", text, ...(text.slice(0, prefix).trim() ? { cache_prefix_length: prefix } : {}) }],
  };

  // Return the message and string prompt
  return {
    message: message,
    prompt: text
  };
}; 