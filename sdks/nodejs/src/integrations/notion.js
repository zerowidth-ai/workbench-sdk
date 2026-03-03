import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

// Current Notion API version
const NOTION_VERSION = '2022-06-28';

export default class NotionIntegration {
    constructor(apiKey, options = {}) {
        this.apiKey = apiKey;
        this.options = {
            baseURL: 'https://api.notion.com/v1',
            timeout: 30000,
            ...options
        };
    }

    /**
     * Make an API request with error handling
     * @param {Object} config - Axios request config
     * @returns {Promise<Object>} Response data
     */
    async _request(config) {
        const requestHeaders = {
            'Authorization': `Bearer ${this.apiKey}`,
            'Content-Type': 'application/json',
            'Notion-Version': NOTION_VERSION,
            ...config.headers
        };
        const startTime = Date.now();

        try {
            const response = await axios({
                ...config,
                headers: requestHeaders,
                timeout: this.options.timeout
            });

            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'notion', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'notion', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });

            if (error.response) {
                const errorBody = JSON.stringify(error.response.data);
                throw new Error(`Notion API error (${error.response.status}): ${errorBody}`);
            }
            throw new Error(`Notion request error: ${error.message}`);
        }
    }

    /**
     * Query a database
     * @param {string} databaseId - The database ID
     * @param {Object} options - Query options
     * @returns {Promise<Object>} Query results
     */
    async queryDatabase(databaseId, options = {}) {
        const body = {};
        if (options.filter) body.filter = options.filter;
        if (options.sorts) body.sorts = options.sorts;
        if (options.startCursor) body.start_cursor = options.startCursor;
        if (options.pageSize) body.page_size = Math.min(options.pageSize, 100);

        return this._request({
            method: 'POST',
            url: `${this.options.baseURL}/databases/${databaseId}/query`,
            data: body
        });
    }

    /**
     * Retrieve a page by ID
     * @param {string} pageId - The page ID
     * @returns {Promise<Object>} Page object
     */
    async getPage(pageId) {
        return this._request({
            method: 'GET',
            url: `${this.options.baseURL}/pages/${pageId}`
        });
    }

    /**
     * Create a new page
     * @param {Object} parent - Parent object (database_id or page_id)
     * @param {Object} properties - Page properties
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} Created page
     */
    async createPage(parent, properties, options = {}) {
        const body = {
            parent,
            properties
        };
        if (options.children) body.children = options.children;
        if (options.icon) body.icon = options.icon;
        if (options.cover) body.cover = options.cover;

        return this._request({
            method: 'POST',
            url: `${this.options.baseURL}/pages`,
            data: body
        });
    }

    /**
     * Update a page's properties
     * @param {string} pageId - The page ID
     * @param {Object} properties - Properties to update
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} Updated page
     */
    async updatePage(pageId, properties, options = {}) {
        const body = {};
        if (properties) body.properties = properties;
        if (options.icon) body.icon = options.icon;
        if (options.cover) body.cover = options.cover;

        return this._request({
            method: 'PATCH',
            url: `${this.options.baseURL}/pages/${pageId}`,
            data: body
        });
    }

    /**
     * Archive or restore a page
     * @param {string} pageId - The page ID
     * @param {boolean} archived - True to archive, false to restore
     * @returns {Promise<Object>} Updated page
     */
    async archivePage(pageId, archived = true) {
        return this._request({
            method: 'PATCH',
            url: `${this.options.baseURL}/pages/${pageId}`,
            data: { archived }
        });
    }

    /**
     * Get children blocks of a block or page
     * @param {string} blockId - The block or page ID
     * @param {Object} options - Pagination options
     * @returns {Promise<Object>} Block children
     */
    async getBlockChildren(blockId, options = {}) {
        const params = new URLSearchParams();
        if (options.startCursor) params.append('start_cursor', options.startCursor);
        if (options.pageSize) params.append('page_size', Math.min(options.pageSize, 100));

        const queryString = params.toString();
        const url = `${this.options.baseURL}/blocks/${blockId}/children${queryString ? '?' + queryString : ''}`;

        return this._request({
            method: 'GET',
            url
        });
    }

    /**
     * Append children blocks to a block or page
     * @param {string} blockId - The block or page ID
     * @param {Array} children - Block objects to append
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} Appended blocks
     */
    async appendBlockChildren(blockId, children, options = {}) {
        const body = { children };
        if (options.after) body.after = options.after;

        return this._request({
            method: 'PATCH',
            url: `${this.options.baseURL}/blocks/${blockId}/children`,
            data: body
        });
    }

    /**
     * Search pages and databases
     * @param {Object} options - Search options
     * @returns {Promise<Object>} Search results
     */
    async search(options = {}) {
        const body = {};
        if (options.query) body.query = options.query;
        if (options.filter) body.filter = options.filter;
        if (options.sort) body.sort = options.sort;
        if (options.startCursor) body.start_cursor = options.startCursor;
        if (options.pageSize) body.page_size = Math.min(options.pageSize, 100);

        return this._request({
            method: 'POST',
            url: `${this.options.baseURL}/search`,
            data: body
        });
    }
}
