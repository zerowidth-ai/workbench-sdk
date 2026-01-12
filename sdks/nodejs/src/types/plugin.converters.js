/**
 * Type converters for the 'plugin' type
 * Converts plugin objects to string representation
 */

/**
 * Convert a plugin object to a string representation
 * @param {Object} plugin - Plugin object
 * @returns {string} String representation of the plugin
 */
export function toString(plugin) {
  if (!plugin || typeof plugin !== 'object') {
    return String(plugin || '');
  }
  
  const parts = [];
  if (plugin.name) parts.push(`name: ${plugin.name}`);
  if (plugin.description) parts.push(`description: ${plugin.description}`);
  if (plugin.type) parts.push(`type: ${plugin.type}`);
  
  return parts.length > 0 ? parts.join(', ') : JSON.stringify(plugin);
}

export default {
  toString
};


