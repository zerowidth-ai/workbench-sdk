import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class SlackIntegration {
    constructor(apiKey, options = {}) {
        this.apiKey = apiKey;
        this.options = {
            baseURL: 'https://slack.com/api',
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

            // Slack returns 200 even on errors, check ok field
            const slackError = response.data && response.data.ok === false ? response.data.error : null;

            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'slack', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: slackError
            });

            if (slackError) {
                throw new Error(`Slack API error: ${slackError}`);
            }

            return response.data;
        } catch (error) {
            if (error.message?.startsWith('Slack API error')) {
                throw error;
            }
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'slack', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                throw new Error(`Slack API error (${error.response.status}): ${error.response.statusText}`);
            }
            throw new Error(`Slack API error: ${error.message}`);
        }
    }

    async postMessage(channel, text, options = {}) {
        const data = { channel, text };
        if (options.thread_ts) data.thread_ts = options.thread_ts;
        if (options.blocks) data.blocks = options.blocks;
        if (options.unfurl_links !== undefined) data.unfurl_links = options.unfurl_links;
        if (options.unfurl_media !== undefined) data.unfurl_media = options.unfurl_media;

        return await this._request({
            method: 'POST',
            url: `${this.options.baseURL}/chat.postMessage`,
            data
        });
    }
}
