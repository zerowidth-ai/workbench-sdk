import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class PineconeIntegration {
    constructor(config, options = {}) {
        if (typeof config === 'object') {
            this.apiKey = config.api_key || config.key;
            this.host = config.host; // e.g. https://my-index-abc123.svc.environment.pinecone.io
        } else {
            this.apiKey = config;
            this.host = options.host;
        }
        this.options = {
            timeout: 30000,
            ...options
        };
    }

    async _request(config) {
        const requestHeaders = { 'Api-Key': this.apiKey, 'Content-Type': 'application/json', ...config.headers };
        const startTime = Date.now();

        try {
            const response = await axios({
                ...config,
                headers: requestHeaders,
                timeout: this.options.timeout
            });

            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'pinecone', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'pinecone', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                const msg = error.response.data?.message || error.response.statusText;
                throw new Error(`Pinecone API error (${error.response.status}): ${msg}`);
            }
            throw new Error(`Pinecone API error: ${error.message}`);
        }
    }

    async query(vector, options = {}) {
        const data = {
            vector,
            topK: options.top_k || 10,
            includeMetadata: options.include_metadata !== false,
            includeValues: options.include_values || false
        };
        if (options.namespace) data.namespace = options.namespace;
        if (options.filter) data.filter = options.filter;

        return await this._request({
            method: 'POST',
            url: `${this.host}/query`,
            data
        });
    }

    async upsert(vectors, namespace = null) {
        const data = { vectors };
        if (namespace) data.namespace = namespace;

        return await this._request({
            method: 'POST',
            url: `${this.host}/vectors/upsert`,
            data
        });
    }
}
