import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class JiraIntegration {
    constructor(config, options = {}) {
        if (typeof config === 'object') {
            this.email = config.email;
            this.apiToken = config.api_token;
            this.domain = config.domain; // e.g. yourcompany.atlassian.net
        } else {
            throw new Error('Jira integration requires an object with email, api_token, and domain');
        }
        this.options = {
            baseURL: `https://${this.domain}/rest/api/3`,
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
                timestamp: startTime, integration: 'jira', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'jira', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                const errors = error.response.data?.errorMessages || [];
                const fieldErrors = error.response.data?.errors || {};
                const msg = errors.length > 0
                    ? errors.join('; ')
                    : Object.entries(fieldErrors).map(([k, v]) => `${k}: ${v}`).join('; ') || error.response.statusText;
                throw new Error(`Jira API error (${error.response.status}): ${msg}`);
            }
            throw new Error(`Jira API error: ${error.message}`);
        }
    }

    async createIssue(projectKey, summary, options = {}) {
        const fields = {
            project: { key: projectKey },
            summary,
            issuetype: { name: options.issueType || 'Task' }
        };

        if (options.description) {
            fields.description = {
                type: 'doc',
                version: 1,
                content: [{
                    type: 'paragraph',
                    content: [{ type: 'text', text: options.description }]
                }]
            };
        }
        if (options.assigneeId) fields.assignee = { accountId: options.assigneeId };
        if (options.priority) fields.priority = { name: options.priority };
        if (options.labels) fields.labels = options.labels;
        if (options.parentKey) fields.parent = { key: options.parentKey };

        return await this._request({
            method: 'POST',
            url: `${this.options.baseURL}/issue`,
            data: { fields }
        });
    }

    async listIssues(jql, options = {}) {
        const data = {
            jql,
            maxResults: options.maxResults ?? 25,
            startAt: options.startAt ?? 0,
            fields: options.fields || ['summary', 'status', 'assignee', 'priority', 'created', 'updated', 'issuetype']
        };

        return await this._request({
            method: 'POST',
            url: `${this.options.baseURL}/search`,
            data
        });
    }

    async updateIssue(issueKey, fields) {
        return await this._request({
            method: 'PUT',
            url: `${this.options.baseURL}/issue/${issueKey}`,
            data: { fields }
        });
    }
}
