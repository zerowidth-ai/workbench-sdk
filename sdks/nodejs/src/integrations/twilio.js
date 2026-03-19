import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class TwilioIntegration {
    constructor(config, options = {}) {
        if (typeof config === 'object') {
            this.accountSid = config.account_sid;
            this.authToken = config.auth_token;
        } else {
            throw new Error('Twilio integration requires an object with account_sid and auth_token');
        }
        this.options = {
            baseURL: `https://api.twilio.com/2010-04-01/Accounts/${this.accountSid}`,
            timeout: 30000,
            ...options
        };
    }

    async _request(config) {
        const requestHeaders = { 'Content-Type': 'application/x-www-form-urlencoded', ...config.headers };
        const startTime = Date.now();

        try {
            const response = await axios({
                ...config,
                headers: requestHeaders,
                auth: { username: this.accountSid, password: this.authToken },
                timeout: this.options.timeout
            });

            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'twilio', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'twilio', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                const msg = error.response.data?.message || error.response.statusText;
                throw new Error(`Twilio API error (${error.response.status}): ${msg}`);
            }
            throw new Error(`Twilio API error: ${error.message}`);
        }
    }

    async sendSMS(to, from, body) {
        const params = new URLSearchParams();
        params.append('To', to);
        params.append('From', from);
        params.append('Body', body);

        return await this._request({
            method: 'POST',
            url: `${this.options.baseURL}/Messages.json`,
            data: params.toString()
        });
    }
}
