import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class StripeIntegration {
    constructor(apiKey, options = {}) {
        this.apiKey = apiKey;
        this.options = {
            baseURL: 'https://api.stripe.com/v1',
            timeout: 30000,
            ...options
        };
    }

    async _request(config) {
        const requestHeaders = {
            'Authorization': `Bearer ${this.apiKey}`,
            'Content-Type': 'application/x-www-form-urlencoded',
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
                timestamp: startTime, integration: 'stripe', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'stripe', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                const msg = error.response.data?.error?.message || error.response.statusText;
                throw new Error(`Stripe API error (${error.response.status}): ${msg}`);
            }
            throw new Error(`Stripe API error: ${error.message}`);
        }
    }

    async listCustomers(options = {}) {
        const params = {};
        if (options.email) params.email = options.email;
        if (options.limit) params.limit = options.limit;
        if (options.starting_after) params.starting_after = options.starting_after;

        return await this._request({
            method: 'GET',
            url: `${this.options.baseURL}/customers`,
            params
        });
    }

    async createCustomer(params = {}) {
        const data = new URLSearchParams();
        if (params.email) data.append('email', params.email);
        if (params.name) data.append('name', params.name);
        if (params.description) data.append('description', params.description);
        if (params.phone) data.append('phone', params.phone);

        return await this._request({
            method: 'POST',
            url: `${this.options.baseURL}/customers`,
            data: data.toString()
        });
    }
}
