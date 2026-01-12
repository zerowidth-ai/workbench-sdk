/**
 * Type converters for the 'message' type
 * Converts message objects to strings by extracting all text content
 */

import { extractTextFromContent } from '../utilities/helpers.js';

/**
 * Convert a message object to a string
 * Joins all text content from the message's content array
 * @param {Object} message - Message object with content field
 * @param {string} separator - Optional separator (not used for single messages)
 * @returns {string} All text content joined together
 */
export function toString(message, separator) {
  if (!message || typeof message !== 'object') {
    return String(message || '');
  }
  
  return extractTextFromContent(message.content);
}

/**
 * Convert a message object to a boolean
 * @param {Object} message - Message object with content field
 * @returns {boolean} True if the message is not undefined or null 
 */
export function toBoolean(message) {
  if (!message || typeof message !== 'object') {
    return false;
  }
  
  return message.content !== undefined && message.content !== null;
}


/**
 * Export the converters object
 * Each key corresponds to a conversion operation (e.g., 'toString')
 */
export default {
  toString,
  toBoolean
};

