/**
 * Type converters for the 'conversation' type
 * Converts an array of messages to a string
 */

import { extractTextFromContent } from '../utilities/helpers.js';

/**
 * Convert a conversation to a YAML-like chat log format
 * This is the default toString behavior for conversations
 * Format: {role}:\n  {content}\n
 * @param {Array} conversation - Array of message objects
 * @param {string} separator - Ignored (kept for API compatibility)
 * @returns {string} YAML-like formatted chat log
 */
export function toString(conversation, separator) {
  if (!Array.isArray(conversation)) {
    return String(conversation || '');
  }
  
  const lines = [];
  
  for (const message of conversation) {
    if (typeof message === 'string') {
      // Simple string message - no role
      lines.push(message);
      lines.push(''); // Empty line separator
      continue;
    }
    
    if (!message || typeof message !== 'object') {
      continue;
    }
    
    // Get role (default to 'unknown' if not specified)
    const role = message.role || 'unknown';
    
    // Format the content
    let contentStr = '';
    
    if (message.content === undefined || message.content === null) {
      // No content
      contentStr = '';
    } else if (typeof message.content === 'string') {
      // Simple string content
      contentStr = message.content;
    } else if (Array.isArray(message.content)) {
      // Array of content items
      const contentParts = message.content
        .map(item => formatContentItem(item))
        .filter(part => part.trim().length > 0);
      contentStr = contentParts.join(' ');
    } else {
      // Fallback
      contentStr = String(message.content);
    }
    
    // Handle tool_call_id
    if (message.tool_call_id) {
      if (contentStr) {
        contentStr += ` [tool_call_id: ${message.tool_call_id}]`;
      } else {
        contentStr = `[tool_call_id: ${message.tool_call_id}]`;
      }
    }
    
    // Format as role: content
    if (contentStr.trim()) {
      lines.push(`${role}:`);
      // Indent content (2 spaces for YAML-like style)
      const indentedContent = contentStr.split('\n').map(line => `  ${line}`).join('\n');
      lines.push(indentedContent);
    } else {
      // Empty content - just show role
      lines.push(`${role}:`);
    }
    
    // Add empty line separator between messages
    lines.push('');
  }
  
  return lines.join('\n').trim();
}

/**
 * Format a single content item for the chat log
 * @param {Object} item - Content item object
 * @returns {string} Formatted string representation
 */
function formatContentItem(item) {
  if (!item || typeof item !== 'object') {
    return '';
  }
  
  const parts = [];
  
  // Handle text content
  if (item.type === 'text' && item.text) {
    parts.push(item.text);
  }
  
  // Handle image URLs
  if (item.image_url && item.image_url.url) {
    parts.push(`[image_url: ${item.image_url.url}]`);
  }
  
  // Handle tool calls
  if (item.type === 'tool_call' || item.name) {
    const toolParts = [];
    if (item.name) toolParts.push(`tool: ${item.name}`);
    if (item.arguments) {
      toolParts.push(`arguments: ${JSON.stringify(item.arguments)}`);
    }
    if (toolParts.length > 0) {
      parts.push(`[${toolParts.join(', ')}]`);
    }
  }
  
  // Handle tool results
  if (item.type === 'tool_result' || item.result !== undefined) {
    const resultStr = typeof item.result === 'string' 
      ? item.result 
      : JSON.stringify(item.result);
    parts.push(`[tool_result: ${resultStr}]`);
  }
  
  // Handle source references
  if (item.source) {
    const sourceParts = [];
    if (item.source.url) sourceParts.push(`url: ${item.source.url}`);
    if (item.source.media_type) sourceParts.push(`media_type: ${item.source.media_type}`);
    if (sourceParts.length > 0) {
      parts.push(`[source: ${sourceParts.join(', ')}]`);
    }
  }
  
  // Handle other types
  if (parts.length === 0 && item.type) {
    parts.push(`[${item.type}]`);
  }
  
  return parts.join(' ');
}

export default {
  toString
};

