/**
 * Process function for the Message node.
 * Outputs a message object, either from the input or from the settings.
 */
/**
 * Render a variable value for injection into message text.
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
    // the default coercion rather than failing the whole message.
    return String(value);
  }
};

/**
 * A token's key and its fallback: `name`, or `name:"Unknown Name"` for the
 * text to use when `name` is missing or empty. Inside the quotes, `\"` is a
 * quote and `\\` a backslash. Same rules as the System Prompt node.
 */
const TOKEN = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*"((?:[^"\\]|\\.)*)")?\s*$/;

const isEmpty = (value) =>
  value === null || value === undefined || (typeof value === "string" && value.trim() === "");

/** The text a `{{…}}` token becomes, or null to leave it as written. */
const resolveToken = (variables, inner) => {
  const exact = variables.find((v) => Object.keys(v).includes(inner));
  if (exact) return renderVariable(exact[inner]);
  const m = TOKEN.exec(inner);
  if (!m) return null;
  const key = m[1];
  const fallback = m[2] === undefined ? undefined : m[2].replace(/\\(.)/g, "$1");
  const found = variables.find((v) => Object.keys(v).includes(key));
  const value = found ? found[key] : undefined;
  if (!isEmpty(value)) return renderVariable(value);
  if (fallback !== undefined) return fallback;
  return found ? renderVariable(value) : null;
};

export default async ({inputs, settings, config}) => {

  // If an input value is provided, use it; otherwise use the value from settings
  let message = {
    role: inputs.role !== undefined ? inputs.role : settings.role,
    content: inputs.content !== undefined ? inputs.content : settings.content
  }

  if(typeof message.content === 'string') {
    message.content = [{ type: 'text', text: message.content }];
  }

  if(!inputs.variables) {
    inputs.variables = [];
  }

  // A single connection can deliver an array of key-value objects, so flatten
  // one level before looking keys up.
  const variables = (Array.isArray(inputs.variables) ? inputs.variables : [inputs.variables])
    .flatMap(entry => Array.isArray(entry) ? entry : [entry])
    .filter(entry => entry !== null && typeof entry === "object");
  
  // if we have variables and text content, we need to replace the text content with the variables
  // do we have a text content item and what index is it
  let textContentIndex = message.content.findIndex(item => item.type === 'text');
  if(textContentIndex !== -1) {
    message.content[textContentIndex].text = message.content[textContentIndex].text.replace(
      /\{\{(.*?)\}\}/g,
      (match, p1) => resolveToken(variables, p1) ?? match,
    );
  }
  
  // Return the string value
  return {
    message: message  
  };
}; 