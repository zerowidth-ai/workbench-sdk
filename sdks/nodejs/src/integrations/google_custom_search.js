import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class GoogleCustomSearchIntegration {
    constructor(apiKey, options = {}) {
        this.apiKey = apiKey?.key;
        this.cx = apiKey?.cx;

        if(!this.apiKey) {
            throw new Error('Google Custom Search API key is required');
        }

        this.options = {
            baseURL: 'https://www.googleapis.com/customsearch/v1',
            timeout: 30000,
            ...options
        };
    }

    /**
     * Perform a custom search using Google Custom Search API
     * @param {Object} params - Search parameters
     * @returns {Promise<Object>} Search response
     */
    async search(params = {}) {
        try {
            const url = this.options.baseURL;

            // Remove any params that are null, undefined, or empty strings
            Object.keys(params).forEach(key => {
                if (params[key] === '') {
                    delete params[key];
                }
                if (params[key] === null) {
                    delete params[key];
                }
                if (params[key] === undefined) {
                    delete params[key];
                }
                if (Array.isArray(params[key]) && params[key].length === 0) {
                    delete params[key];
                }
            });

            const queryParams = { key: this.apiKey, cx: this.cx, ...params };
            const startTime = Date.now();
            // Build full URL with query params for event (sanitizer will redact key)
            const fullUrl = `${url}?${new URLSearchParams(queryParams).toString()}`;

            const response = await axios({
                url: url,
                method: 'GET',
                params: queryParams,
                timeout: this.options.timeout
            });

            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'google_custom_search', nodeId: null, nodeType: null,
                request: { method: 'GET', url: fullUrl, headers: {}, body: null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            if (response.status >= 400) {
                throw new Error(`Google Custom Search API error: ${response.status} - ${response.data?.error?.message || response.statusText}`);
            }

            return response.data;

        } catch (error) {
            if (error.response) {
                const status = error.response.status;
                const statusText = error.response.statusText;
                const responseData = error.response.data;
                
                let errorMessage = `Google Custom Search API Error (${status} ${statusText})`;
                if (responseData?.error?.message) {
                    errorMessage += `: ${responseData.error.message}`;
                } else if (responseData?.error) {
                    errorMessage += `: ${responseData.error}`;
                }
                
                throw new Error(errorMessage);
            } else if (error.request) {
                throw new Error('Google Custom Search API Error: No response received');
            } else {
                throw new Error(`Google Custom Search API Error: ${error.message}`);
            }
        }
    }

    /**
     * Helper function to convert comma-separated string to array
     * @param {string|Array} input - String or array input
     * @returns {Array} Array of strings
     */
    static stringToArray(input) {
        if (Array.isArray(input)) {
            return input;
        }
        if (typeof input === 'string') {
            return input.split(',').map(item => item.trim()).filter(item => item.length > 0);
        }
        return [];
    }

    /**
     * Helper function to build query parameters with array handling
     * @param {Object} params - Raw parameters
     * @returns {Object} Processed parameters
     */
    static processParams(params) {
        const processed = { ...params };
        
        // Fields that should be converted from comma-separated strings to arrays
        const arrayFields = [
            'excludeTerms', 'fileType', 'rights', 'safe'
        ];

        arrayFields.forEach(field => {
            if (processed[field] !== undefined) {
                const arrayValue = this.stringToArray(processed[field]);
                if (arrayValue.length > 0) {
                    processed[field] = arrayValue.join(' ');
                }
            }
        });

        // Special handling for searchType - only include if it's "image"
        if (processed.searchType && processed.searchType !== 'image') {
            delete processed.searchType;
        }

        return processed;
    }
}
