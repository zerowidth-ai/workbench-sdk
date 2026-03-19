import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class LinearIntegration {
    constructor(apiKey, options = {}) {
        this.apiKey = apiKey;
        this.options = {
            baseURL: 'https://api.linear.app',
            timeout: 30000,
            ...options
        };
    }

    async _graphql(query, variables = {}) {
        const requestHeaders = { 'Authorization': this.apiKey, 'Content-Type': 'application/json' };
        const startTime = Date.now();
        const data = { query, variables };

        try {
            const response = await axios({
                method: 'POST',
                url: `${this.options.baseURL}/graphql`,
                headers: requestHeaders,
                data,
                timeout: this.options.timeout
            });

            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'linear', nodeId: null, nodeType: null,
                request: { method: 'POST', url: `${this.options.baseURL}/graphql`, headers: requestHeaders, body: data },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            if (response.data.errors) {
                throw new Error(`Linear API error: ${response.data.errors.map(e => e.message).join('; ')}`);
            }

            return response.data.data;
        } catch (error) {
            if (error.message?.startsWith('Linear API error')) throw error;
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'linear', nodeId: null, nodeType: null,
                request: { method: 'POST', url: `${this.options.baseURL}/graphql`, headers: requestHeaders, body: data },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                throw new Error(`Linear API error (${error.response.status}): ${error.response.statusText}`);
            }
            throw new Error(`Linear API error: ${error.message}`);
        }
    }

    async createIssue(teamId, title, options = {}) {
        const mutation = `
            mutation IssueCreate($input: IssueCreateInput!) {
                issueCreate(input: $input) {
                    success
                    issue {
                        id
                        identifier
                        title
                        url
                        state { name }
                        priority
                        createdAt
                    }
                }
            }
        `;

        const input = { teamId, title };
        if (options.description) input.description = options.description;
        if (options.priority) input.priority = options.priority;
        if (options.assigneeId) input.assigneeId = options.assigneeId;
        if (options.labelIds) input.labelIds = options.labelIds;
        if (options.stateId) input.stateId = options.stateId;

        const result = await this._graphql(mutation, { input });
        return result.issueCreate;
    }

    async listIssues(options = {}) {
        const query = `
            query Issues($filter: IssueFilter, $first: Int, $after: String) {
                issues(filter: $filter, first: $first, after: $after) {
                    nodes {
                        id
                        identifier
                        title
                        url
                        state { name }
                        priority
                        assignee { name email }
                        createdAt
                        updatedAt
                    }
                    pageInfo { hasNextPage endCursor }
                }
            }
        `;

        const variables = {};
        if (options.first) variables.first = options.first;
        if (options.after) variables.after = options.after;
        if (options.filter) variables.filter = options.filter;

        const result = await this._graphql(query, variables);
        return result.issues;
    }

    async updateIssue(issueId, updates) {
        const mutation = `
            mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
                issueUpdate(id: $id, input: $input) {
                    success
                    issue {
                        id
                        identifier
                        title
                        url
                        state { name }
                        priority
                        updatedAt
                    }
                }
            }
        `;

        const result = await this._graphql(mutation, { id: issueId, input: updates });
        return result.issueUpdate;
    }
}
