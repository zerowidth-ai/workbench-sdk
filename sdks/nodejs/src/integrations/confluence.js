import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class ConfluenceIntegration {
    constructor(config, options = {}) {
        if (typeof config === 'object') {
            this.email = config.email;
            this.apiToken = config.api_token;
            this.domain = config.domain; // e.g. yourcompany.atlassian.net
        } else {
            throw new Error('Confluence integration requires an object with email, api_token, and domain');
        }
        this.options = {
            baseURL: `https://${this.domain}/wiki/api/v2`,
            timeout: 30000,
            ...options
        };
    }

    async _request(config) {
        const auth = Buffer.from(`${this.email}:${this.apiToken}`).toString('base64');
        const requestHeaders = {
            'Authorization': `Basic ${auth}`,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
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
                timestamp: startTime, integration: 'confluence', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'confluence', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                const msg = error.response.data?.message || error.response.statusText;
                throw new Error(`Confluence API error (${error.response.status}): ${msg}`);
            }
            throw new Error(`Confluence API error: ${error.message}`);
        }
    }

    async search(query, options = {}) {
        const params = {
            query,
            limit: options.limit ?? 25
        };
        if (options.cursor) params.cursor = options.cursor;
        if (options.spaceKey) params.spaceKey = options.spaceKey;

        // CQL search via v1 API (v2 doesn't have full CQL support yet)
        const searchUrl = `https://${this.domain}/wiki/rest/api/content/search`;
        return await this._request({
            method: 'GET',
            url: searchUrl,
            params: { cql: query, limit: params.limit, start: options.start ?? 0 }
        });
    }

    async getPage(pageId, options = {}) {
        const params = {};
        if (options.bodyFormat) params['body-format'] = options.bodyFormat;

        return await this._request({
            method: 'GET',
            url: `${this.options.baseURL}/pages/${pageId}`,
            params
        });
    }
}
