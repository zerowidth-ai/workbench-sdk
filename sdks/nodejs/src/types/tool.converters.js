/**
 * Type converters for the 'tool' type
 * Converts tool objects to string representation
 */

/**
 * Convert a tool object to a string representation
 * @param {Object} tool - Tool object
 * @returns {string} String representation of the tool
 */
export function toString(tool) {
  if (!tool || typeof tool !== 'object') {
    return String(tool || '');
  }
  
  const parts = [];
  if (tool.name) parts.push(`name: ${tool.name}`);
  if (tool.description) parts.push(`description: ${tool.description}`);
  if (tool.type) parts.push(`type: ${tool.type}`);
  
  return parts.length > 0 ? parts.join(', ') : JSON.stringify(tool);
}

export default {
  toString
};


