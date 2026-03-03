import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

/**
 * Call an MCP tool
 * @param {Object} args - The arguments to pass to the tool (must include 'name')
 * @param {Object} options - { url, token }
 * @returns {Object} The result of the tool call
 */
export async function callMCPTool(args, { url, token } = {}) {
  if (!url) throw new Error('No MCP URL provided');

  const toolName = args.name;
  if (!toolName) throw new Error('No tool name provided for MCP call');

  const { name, ...toolArgs } = args;
  const id = uuidv4();

  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await axios.post(url, {
      id,
      method: "tools/call",
      params: {
        name: toolName,
        arguments: toolArgs
      }
    }, { headers });
    return response.data?.result;
  } catch (err) {
    throw new Error(`Failed to call MCP tool "${toolName}" at ${url}: ${err.message}`);
  }
}

/**
 * Fetch all tool schemas from an MCP endpoint
 * @param {string} url - The MCP server URL
 * @param {string} [token] - Optional bearer token for authentication
 * @returns {Array} Array of tool schemas
 */
export async function fetchMCPTools(url, token) {
  if (!url) throw new Error('No MCP URL provided');

  const id = uuidv4();

  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await axios.post(url, {
      id,
      method: "tools/list",
      params: {}
    }, { headers });
    const tools = response.data?.result?.tools || [];
    return tools.map(tool => ({
      name: tool.name,
      description: tool.description,
      parameters: tool.inputSchema
    }));
  } catch (err) {
    throw new Error(`Failed to fetch MCP tools from ${url}: ${err.message}`);
  }
}
