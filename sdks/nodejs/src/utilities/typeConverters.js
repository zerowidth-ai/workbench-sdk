/**
 * Type conversion utilities for custom types
 * This module provides utilities for loading and using type converters
 * from separate converter files (e.g., message.converters.js)
 */

/**
 * Load type converters from a converters module if it exists
 * This allows extending converters for custom types
 * @param {string} typeName - The type name
 * @returns {Promise<Object|null>} Converter object or null if not found
 */
export async function loadTypeConverter(typeName) {
  try {
    const { getDirname } = await import('./helpers.js');
    const path = (await import('path')).default;
    const fs = (await import('fs')).default;
    
    const typeDir = path.join(getDirname(import.meta.url), "../types");
    const converterPath = path.join(typeDir, `${typeName}.converters.js`);
    
    if (fs.existsSync(converterPath)) {
      const converterFileUrl = `file://${path.resolve(converterPath)}`;
      const converterModule = await import(converterFileUrl);
      return converterModule.default || converterModule;
    }
  } catch (err) {
    // Converter file doesn't exist or failed to load - that's okay
    return null;
  }
  
  return null;
}

