import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class ResendIntegration {
    constructor(apiKey, options = {}) {
        this.apiKey = apiKey;
        this.options = {
            baseURL: 'https://api.resend.com',
            timeout: 30000,
            ...options
        };
    }

    async _request(config) {
        const requestHeaders = { 'Authorization': `Bearer ${this.apiKey}`, 'Content-Type': 'application/json', ...config.headers };
        const startTime = Date.now();

        try {
            const response = await axios({
                ...config,
                headers: requestHeaders,
                timeout: this.options.timeout
            });

            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'resend', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'resend', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                const msg = error.response.data?.message || error.response.statusText;
                throw new Error(`Resend API error (${error.response.status}): ${msg}`);
            }
            throw new Error(`Resend API error: ${error.message}`);
        }
    }

    async sendEmail(params) {
        const { to, from, subject, text, html, replyTo, cc, bcc } = params;

        const data = { from, subject };

        // to can be string or array
        data.to = typeof to === 'string' ? to.split(',').map(e => e.trim()) : to;

        if (cc) {
            data.cc = typeof cc === 'string' ? cc.split(',').map(e => e.trim()) : cc;
        }
        if (bcc) {
            data.bcc = typeof bcc === 'string' ? bcc.split(',').map(e => e.trim()) : bcc;
        }
        if (text) data.text = text;
        if (html) data.html = html;
        if (replyTo) data.reply_to = replyTo;

        if (!text && !html) {
            throw new Error('Either text or html content is required');
        }

        return await this._request({
            method: 'POST',
            url: `${this.options.baseURL}/emails`,
            data
        });
    }
}
