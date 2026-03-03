import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class AirtableIntegration {
    constructor(apiKey, options = {}) {
        this.apiKey = apiKey;
        this.options = {
            baseURL: 'https://api.airtable.com/v0',
            timeout: 30000,
            ...options
        };
    }

    /**
     * Build the API URL for a table or record
     * @param {string} baseId - The Airtable base ID
     * @param {string} tableName - The table name or ID
     * @param {string} [recordId] - Optional record ID
     * @returns {string} The full API URL
     */
    _buildUrl(baseId, tableName, recordId = null) {
        const encodedTable = encodeURIComponent(tableName);
        let url = `${this.options.baseURL}/${baseId}/${encodedTable}`;
        if (recordId) {
            url = `${url}/${recordId}`;
        }
        return url;
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
                timestamp: startTime, integration: 'airtable', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            return response.data;
        } catch (error) {
            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'airtable', nodeId: null, nodeType: null,
                request: { method: config.method, url: config.url, headers: requestHeaders, body: config.data || null },
                response: { status: error.response?.status || 0, statusText: error.response?.statusText || 'Error' },
                duration: Date.now() - startTime, error: error.message
            });
            if (error.response) {
                const status = error.response.status;
                const errorData = error.response.data?.error || {};
                const errorType = errorData.type || 'UNKNOWN_ERROR';
                const errorMessage = errorData.message || error.response.statusText;
                throw new Error(`Airtable API error (${status}): ${errorType} - ${errorMessage}`);
            } else if (error.request) {
                throw new Error('Airtable API error: No response received');
            } else {
                throw new Error(`Airtable API error: ${error.message}`);
            }
        }
    }

    /**
     * List records from a table
     * @param {string} baseId - The Airtable base ID
     * @param {string} tableName - The table name or ID
     * @param {Object} [params] - Query parameters
     * @returns {Promise<Object>} Response with records and optional offset
     */
    async listRecords(baseId, tableName, params = {}) {
        const url = this._buildUrl(baseId, tableName);
        const queryParams = {};

        if (params.filterFormula) {
            queryParams.filterByFormula = params.filterFormula;
        }
        if (params.sortField) {
            queryParams['sort[0][field]'] = params.sortField;
            queryParams['sort[0][direction]'] = params.sortDirection || 'asc';
        }
        if (params.maxRecords) {
            queryParams.maxRecords = params.maxRecords;
        }
        if (params.pageSize) {
            queryParams.pageSize = Math.min(params.pageSize, 100);
        }
        if (params.offset) {
            queryParams.offset = params.offset;
        }
        if (params.view) {
            queryParams.view = params.view;
        }
        if (params.fields && Array.isArray(params.fields)) {
            params.fields.forEach((field, i) => {
                queryParams[`fields[${i}]`] = field;
            });
        }

        return await this._request({
            method: 'GET',
            url,
            params: queryParams
        });
    }

    /**
     * Get a single record by ID
     * @param {string} baseId - The Airtable base ID
     * @param {string} tableName - The table name or ID
     * @param {string} recordId - The record ID
     * @returns {Promise<Object>} The record
     */
    async getRecord(baseId, tableName, recordId) {
        const url = this._buildUrl(baseId, tableName, recordId);
        return await this._request({
            method: 'GET',
            url
        });
    }

    /**
     * Create a new record
     * @param {string} baseId - The Airtable base ID
     * @param {string} tableName - The table name or ID
     * @param {Object} fields - Field name/value pairs
     * @param {Object} [options] - Additional options
     * @returns {Promise<Object>} The created record
     */
    async createRecord(baseId, tableName, fields, options = {}) {
        const url = this._buildUrl(baseId, tableName);
        const data = { fields };
        if (options.typecast) {
            data.typecast = true;
        }

        return await this._request({
            method: 'POST',
            url,
            data
        });
    }

    /**
     * Update an existing record
     * @param {string} baseId - The Airtable base ID
     * @param {string} tableName - The table name or ID
     * @param {string} recordId - The record ID
     * @param {Object} fields - Field name/value pairs to update
     * @param {Object} [options] - Additional options
     * @returns {Promise<Object>} The updated record
     */
    async updateRecord(baseId, tableName, recordId, fields, options = {}) {
        const url = this._buildUrl(baseId, tableName, recordId);
        const data = { fields };
        if (options.typecast) {
            data.typecast = true;
        }

        return await this._request({
            method: 'PATCH',
            url,
            data
        });
    }

    /**
     * Delete a record
     * @param {string} baseId - The Airtable base ID
     * @param {string} tableName - The table name or ID
     * @param {string} recordId - The record ID
     * @returns {Promise<Object>} Deletion confirmation
     */
    async deleteRecord(baseId, tableName, recordId) {
        const url = this._buildUrl(baseId, tableName, recordId);
        return await this._request({
            method: 'DELETE',
            url
        });
    }
}
