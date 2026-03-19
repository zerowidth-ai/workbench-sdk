import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class SupabaseIntegration {
    constructor(config, options = {}) {
        if (typeof config === 'object') {
            this.url = config.url;
            this.apiKey = config.key || config.api_key;
        } else {
            throw new Error('Supabase integration requires an object with url and key');
        }
        this.options = {
            timeout: 30000,
            ...options
        };
    }

    async _request(config) {
        const requestHeaders = {
            'apikey': this.apiKey,
            'Authorization': `Bearer ${this.apiKey}`,
            'Content-Type': 'application/json',
            'Prefer': config.prefer || 'return=representation',
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
                timestamp: startTime, integration: 'supabase', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'supabase', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                const msg = error.response.data?.message || error.response.data?.error || error.response.statusText;
                throw new Error(`Supabase API error (${error.response.status}): ${msg}`);
            }
            throw new Error(`Supabase API error: ${error.message}`);
        }
    }

    async query(table, options = {}) {
        let url = `${this.url}/rest/v1/${encodeURIComponent(table)}`;
        const params = {};

        if (options.select) params.select = options.select;
        if (options.filter) {
            // filter is an array of {column, operator, value}
            for (const f of (Array.isArray(options.filter) ? options.filter : [options.filter])) {
                params[f.column] = `${f.operator}.${f.value}`;
            }
        }
        if (options.order) params.order = options.order;
        if (options.limit) {
            params.limit = options.limit;
        }
        if (options.offset) params.offset = options.offset;

        return await this._request({ method: 'GET', url, params });
    }

    async insert(table, records) {
        const url = `${this.url}/rest/v1/${encodeURIComponent(table)}`;
        return await this._request({ method: 'POST', url, data: records });
    }

    async update(table, updates, filter) {
        const url = `${this.url}/rest/v1/${encodeURIComponent(table)}`;
        const params = {};
        if (filter) {
            for (const f of (Array.isArray(filter) ? filter : [filter])) {
                params[f.column] = `${f.operator}.${f.value}`;
            }
        }
        return await this._request({ method: 'PATCH', url, params, data: updates });
    }

    async deleteRows(table, filter) {
        const url = `${this.url}/rest/v1/${encodeURIComponent(table)}`;
        const params = {};
        if (filter) {
            for (const f of (Array.isArray(filter) ? filter : [filter])) {
                params[f.column] = `${f.operator}.${f.value}`;
            }
        }
        return await this._request({ method: 'DELETE', url, params });
    }
}
