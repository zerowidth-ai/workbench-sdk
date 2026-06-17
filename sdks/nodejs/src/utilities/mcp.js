import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

/**
 * MCP client for the `remote-mcp-tool` node.
 *
 * Speaks JSON-RPC 2.0 over the Streamable HTTP transport defined by
 * the Model Context Protocol spec:
 *
 *   https://modelcontextprotocol.io/specification
 *
 * Spec-relevant wire requirements (all enforced by reference servers
 * like @modelcontextprotocol/sdk's StreamableHTTPServerTransport):
 *
 *   1. Every request body carries `jsonrpc: "2.0"` plus `id` /
 *      `method` / `params` — the JSON-RPC envelope, not just the
 *      params.
 *   2. `Accept` header MUST list both `application/json` AND
 *      `text/event-stream` — the server picks the response shape
 *      based on whether it's streaming.
 *   3. The response body is either:
 *        - `Content-Type: application/json` — single JSON-RPC
 *          response object, parse normally.
 *        - `Content-Type: text/event-stream` — SSE wire shape;
 *          last `data:` line carries the JSON-RPC response.
 *      Both shapes are valid; this client handles either.
 */

/** Build the headers for an MCP request. Adds bearer auth when
 *  provided; sets the Accept header to satisfy spec-compliant
 *  servers that require both content types in the list. */
function buildHeaders(token) {
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json, text/event-stream',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/** Parse an MCP HTTP response. Tolerates either content-type
 *  variant (plain JSON or SSE-framed). Returns the JSON-RPC
 *  response object's `.result` (or throws on `.error`). */
function parseMcpResponse(response) {
  const contentType = (response.headers?.['content-type'] || '').toLowerCase();

  // Streamable HTTP servers default to SSE — body is one or more
  // `event: ...\ndata: ...\n\n` blocks. Find the final `data:` line
  // and JSON.parse it. We disabled axios' default JSON parse so
  // `response.data` is the raw text either way.
  if (contentType.includes('text/event-stream')) {
    const raw = typeof response.data === 'string'
      ? response.data
      : String(response.data ?? '');
    const dataLines = [];
    for (const line of raw.split(/\r?\n/)) {
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
    }
    if (dataLines.length === 0) {
      throw new Error('MCP SSE response had no data lines');
    }
    const payload = JSON.parse(dataLines[dataLines.length - 1]);
    if (payload.error) {
      throw new Error(
        `MCP error ${payload.error.code}: ${payload.error.message}`,
      );
    }
    return payload.result;
  }

  // Plain JSON response — single JSON-RPC object. `response.data`
  // is the raw text (we disabled axios' parse); JSON.parse here.
  const raw = typeof response.data === 'string'
    ? response.data
    : JSON.stringify(response.data);
  const payload = JSON.parse(raw);
  if (payload?.error) {
    throw new Error(
      `MCP error ${payload.error.code}: ${payload.error.message}`,
    );
  }
  return payload?.result;
}

/**
 * Call an MCP tool.
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

  try {
    const response = await axios.post(
      url,
      {
        jsonrpc: '2.0',
        id,
        method: 'tools/call',
        params: {
          name: toolName,
          arguments: toolArgs,
        },
      },
      {
        headers: buildHeaders(token),
        // SSE responses arrive as text; tell axios not to JSON.parse.
        responseType: 'text',
        transformResponse: [(d) => d],
      },
    );
    return parseMcpResponse(response);
  } catch (err) {
    throw new Error(
      `Failed to call MCP tool "${toolName}" at ${url}: ${err.message}`,
    );
  }
}

/**
 * Fetch all tool schemas from an MCP endpoint.
 * @param {string} url - The MCP server URL
 * @param {string} [token] - Optional bearer token for authentication
 * @returns {Array} Array of tool schemas (normalized to {name, description, parameters})
 */
export async function fetchMCPTools(url, token) {
  if (!url) throw new Error('No MCP URL provided');

  const id = uuidv4();

  try {
    const response = await axios.post(
      url,
      {
        jsonrpc: '2.0',
        id,
        method: 'tools/list',
        params: {},
      },
      {
        headers: buildHeaders(token),
        responseType: 'text',
        transformResponse: [(d) => d],
      },
    );
    const result = parseMcpResponse(response);
    const tools = result?.tools || [];
    return tools.map((tool) => ({
      name: tool.name,
      description: tool.description,
      parameters: tool.inputSchema,
    }));
  } catch (err) {
    throw new Error(`Failed to fetch MCP tools from ${url}: ${err.message}`);
  }
}
