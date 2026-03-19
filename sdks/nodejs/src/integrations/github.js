import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class GithubIntegration {
    constructor(apiKey, options = {}) {
        this.apiKey = apiKey;
        this.options = {
            baseURL: 'https://api.github.com',
            timeout: 30000,
            ...options
        };
    }

    async _request(config) {
        const requestHeaders = {
            'Authorization': `Bearer ${this.apiKey}`,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
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
                timestamp: startTime, integration: 'github', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'github', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                const msg = error.response.data?.message || error.response.statusText;
                throw new Error(`GitHub API error (${error.response.status}): ${msg}`);
            }
            throw new Error(`GitHub API error: ${error.message}`);
        }
    }

    async createIssue(owner, repo, title, options = {}) {
        const data = { title };
        if (options.body) data.body = options.body;
        if (options.labels) data.labels = options.labels;
        if (options.assignees) data.assignees = options.assignees;

        return await this._request({
            method: 'POST',
            url: `${this.options.baseURL}/repos/${owner}/${repo}/issues`,
            data
        });
    }

    async listIssues(owner, repo, options = {}) {
        const params = {};
        if (options.state) params.state = options.state;
        if (options.labels) params.labels = options.labels;
        if (options.per_page) params.per_page = options.per_page;
        if (options.page) params.page = options.page;

        return await this._request({
            method: 'GET',
            url: `${this.options.baseURL}/repos/${owner}/${repo}/issues`,
            params
        });
    }
}
