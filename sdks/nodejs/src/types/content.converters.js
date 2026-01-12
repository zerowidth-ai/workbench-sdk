/**
 * Type converters for the 'content' type
 * Extracts text from content objects/arrays
 */

import { extractTextFromContent } from '../utilities/helpers.js';

/**
 * Convert a content object to a string
 * Extracts text from content items with type 'text'
 * @param {Object|Array|string} content - Content object, array, or string
 * @returns {string} Extracted text content
 */
export function toString(content) {
  return extractTextFromContent(content);
}

export default {
  toString
};

