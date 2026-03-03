import axios from 'axios';
import { emitAPICallEvent } from '../utilities/sanitizeAPICall.js';

export default class NewsDataIntegration {
    constructor(apiKey, options = {}) {
        this.apiKey = apiKey;
        this.options = {
            baseURL: 'https://newsdata.io/api/1',
            timeout: 30000,
            ...options
        };
    }

    /**
     * Make a request to any NewsData.io endpoint
     * @param {string} endpoint - The endpoint path (e.g., 'latest', 'archive', 'crypto', 'news', 'sources')
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} API response
     */
    async request(endpoint, params = {}) {
        try {
            const url = `${this.options.baseURL}/${endpoint}`;

            // remove any params that are just empty strings
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
              if (params[key] === false) {
                delete params[key];
              }
              if (Array.isArray(params[key]) && params[key].length === 0) {
                delete params[key];
              }

              // change any params that are true to 1
              if (params[key] === true) {
                params[key] = 1;
              }

            });


            const queryParams = { apikey: this.apiKey, ...params };
            const startTime = Date.now();
            const fullUrl = `${url}?${new URLSearchParams(queryParams).toString()}`;

            const response = await axios({
                url: url,
                method: 'GET',
                params: queryParams,
                timeout: this.options.timeout
            });

            await emitAPICallEvent(this._engineConfig, {
                timestamp: startTime, integration: 'newsdata_io', nodeId: null, nodeType: null,
                request: { method: 'GET', url: fullUrl, headers: {}, body: null },
                response: { status: response.status, statusText: response.statusText },
                duration: Date.now() - startTime, error: null
            });

            if (response.status >= 400) {
                throw new Error(`NewsData API error: ${response.status} - ${response.data?.message || response.statusText}`);
            }

            return response.data;

        } catch (error) {
            if (error.response) {
                const status = error.response.status;
                const statusText = error.response.statusText;
                const responseData = error.response.data;
                
                let errorMessage = `NewsData API Error (${status} ${statusText})`;
                if (responseData?.message) {
                    errorMessage += `: ${responseData.message}`;
                }
                
                throw new Error(errorMessage);
            } else if (error.request) {
                throw new Error('NewsData API Error: No response received');
            } else {
                throw new Error(`NewsData API Error: ${error.message}`);
            }
        }
    }

    /**
     * Get latest news from the last 48 hours
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Latest news response
     */
    async getLatest(params = {}) {
        return await this.request('latest', params);
    }

    /**
     * Get historical news from archive
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Archive news response
     */
    async getArchive(params = {}) {
        return await this.request('archive', params);
    }

    /**
     * Get breaking/real-time news
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Breaking news response
     */
    async getBreaking(params = {}) {
        return await this.request('news', params);
    }

    /**
     * Get crypto-specific news
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Crypto news response
     */
    async getCrypto(params = {}) {
        return await this.request('crypto', params);
    }

    /**
     * Get list of source domains
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Sources response
     */
    async getSources(params = {}) {
        return await this.request('sources', params);
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
        
        // Handle parameter name mappings (snake_case input names to API parameter names)
        const paramMappings = {
            'categories': 'category',
            'exclude_categories': 'excludecategory',
            'countries': 'country',
            'regions': 'region',
            'languages': 'language',
            'domains': 'domain',
            'exclude_domains': 'excludedomain',
            'exclude_fields': 'excludefield',
            'coins': 'coin'
        };
        
        // Apply parameter name mappings
        Object.entries(paramMappings).forEach(([inputKey, apiKey]) => {
            if (processed[inputKey] !== undefined) {
                processed[apiKey] = processed[inputKey];
                delete processed[inputKey]; // Remove the old key
            }
        });
        
        // Fields that should be converted from comma-separated strings to arrays
        const arrayFields = [
            'country', 'region', 'category', 'excludecategory',
            'language', 'domain', 'excludedomain', 'excludefield',
            'coin'
        ];

        arrayFields.forEach(field => {
            if (processed[field] !== undefined) {
                const arrayValue = this.stringToArray(processed[field]);
                if (arrayValue.length > 0) {
                    processed[field] = arrayValue.join(',');
                }
            }
        });

        return processed;
    }
}
