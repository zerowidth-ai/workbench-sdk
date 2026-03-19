import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class SendGridIntegration {
    constructor(apiKey, options = {}) {
        this.apiKey = apiKey;
        this.options = {
            baseURL: 'https://api.sendgrid.com/v3',
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
        const requestHeaders = { 'Authorization': `Bearer ${this.apiKey}`, 'Content-Type': 'application/json', ...config.headers };
        const startTime = Date.now();

        try {
            const response = await axios({
                ...config,
                headers: requestHeaders,
                timeout: this.options.timeout
            });

            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'sendgrid', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'sendgrid', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                const status = error.response.status;
                const errors = error.response.data?.errors;
                const errorMessage = errors && errors.length > 0
                    ? errors.map(e => e.message).join('; ')
                    : error.response.statusText;
                throw new Error(`SendGrid API error (${status}): ${errorMessage}`);
            } else if (error.request) {
                throw new Error('SendGrid API error: No response received');
            } else {
                throw new Error(`SendGrid API error: ${error.message}`);
            }
        }
    }

    /**
     * Send an email using the SendGrid Mail Send API
     * @param {Object} params - Email parameters
     * @param {string} params.to - Recipient email address(es), comma-separated for multiple
     * @param {string} params.from - Sender email address
     * @param {string} [params.fromName] - Sender display name
     * @param {string} params.subject - Email subject
     * @param {string} [params.text] - Plain text body
     * @param {string} [params.html] - HTML body
     * @param {string} [params.replyTo] - Reply-to email address
     * @param {Array} [params.cc] - CC email addresses
     * @param {Array} [params.bcc] - BCC email addresses
     * @returns {Promise<Object>} Response with status
     */
    async sendEmail(params) {
        const { to, from, fromName, subject, text, html, replyTo, cc, bcc } = params;

        // Build personalizations
        const toAddresses = (typeof to === 'string' ? to.split(',') : to).map(email => ({ email: email.trim() }));
        const personalization = { to: toAddresses };

        if (cc && cc.length > 0) {
            personalization.cc = (typeof cc === 'string' ? cc.split(',') : cc).map(email => ({ email: email.trim() }));
        }
        if (bcc && bcc.length > 0) {
            personalization.bcc = (typeof bcc === 'string' ? bcc.split(',') : bcc).map(email => ({ email: email.trim() }));
        }

        // Build content
        const content = [];
        if (text) {
            content.push({ type: 'text/plain', value: text });
        }
        if (html) {
            content.push({ type: 'text/html', value: html });
        }
        if (content.length === 0) {
            throw new Error('Either text or html content is required');
        }

        // Build request body
        const data = {
            personalizations: [personalization],
            from: fromName ? { email: from, name: fromName } : { email: from },
            subject,
            content
        };

        if (replyTo) {
            data.reply_to = { email: replyTo };
        }

        return await this._request({
            method: 'POST',
            url: `${this.options.baseURL}/mail/send`,
            data
        });
    }
}
