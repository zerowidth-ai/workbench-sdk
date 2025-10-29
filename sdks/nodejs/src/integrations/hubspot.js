import axios from 'axios';
import { isOAuthKey, OAuthRefreshManager } from '../utilities/oauth.js';

export default class HubSpotIntegration {
  constructor(oauthKey, options = {}) {
    if (!isOAuthKey(oauthKey)) {
      throw new Error('HubSpot integration requires an OAuth key with accessToken and onRefresh');
    }

    this.oauthKey = oauthKey;
    this.options = {
      baseURL: 'https://api.hubapi.com',
      timeout: 30000,
      ...options
    };

    // Initialize OAuth refresh manager
    // Note: config will be set when integration is loaded with full config
    this.refreshManager = null;
  }

  /**
   * Set the OAuth refresh manager (called during integration loading)
   * @param {OAuthRefreshManager} refreshManager - The refresh manager instance
   */
  setRefreshManager(refreshManager) {
    this.refreshManager = refreshManager;
  }

  /**
   * Update OAuth key (called after refresh)
   * @param {Object} updatedKey - Updated OAuth key object
   */
  updateOAuthKey(updatedKey) {
    this.oauthKey = { ...this.oauthKey, ...updatedKey };
  }

  /**
   * Make an API request to HubSpot with automatic OAuth token refresh
   * @param {string} method - HTTP method (GET, POST, etc.)
   * @param {string} url - API endpoint (relative to baseURL)
   * @param {Object} options - Request options (headers, data, params, etc.)
   * @returns {Promise<Object>} API response data
   */
  async request(method, url, options = {}) {
    if (!this.refreshManager) {
      throw new Error('OAuth refresh manager not initialized. This integration requires engine config context.');
    }

    // Ensure absolute URL
    const fullUrl = url.startsWith('http') ? url : `${this.options.baseURL}${url}`;

    // Ensure token is valid before making request
    this.oauthKey = await this.refreshManager.ensureValidToken('hubspot', this.oauthKey);
    this.updateOAuthKey(this.oauthKey);

    // Make request with retry logic for expired tokens
    let lastError = null;
    let retries = 0;
    const maxRetries = 2; // Initial attempt + 1 retry after refresh

    while (retries <= maxRetries) {
      try {
        const response = await axios({
          method,
          url: fullUrl,
          headers: {
            'Authorization': `Bearer ${this.oauthKey.accessToken}`,
            'Content-Type': 'application/json',
            ...options.headers
          },
          data: options.data,
          params: options.params,
          timeout: options.timeout || this.options.timeout,
          validateStatus: () => true // Don't throw on HTTP errors
        });

        // Check if response indicates token refresh is needed
        if (OAuthRefreshManager.needsRefresh(response, this._checkHubSpotError)) {
          if (retries < maxRetries) {
            // Refresh token and retry
            this.oauthKey = await this.refreshManager.refreshToken('hubspot', this.oauthKey);
            this.updateOAuthKey(this.oauthKey);
            retries++;
            continue;
          } else {
            throw new Error(`HubSpot API error: ${response.status} - Token refresh failed`);
          }
        }

        // Check for other HTTP errors
        if (response.status >= 400) {
          const errorMessage = this._extractErrorMessage(response);
          throw new Error(`HubSpot API error: ${response.status} - ${errorMessage}`);
        }

        return response.data;
      } catch (error) {
        // If it's an OAuth refresh error, throw immediately
        if (error.message && error.message.includes('OAuth refresh failed')) {
          throw error;
        }

        // For other errors, try refresh if we haven't exhausted retries
        if (retries < maxRetries && !lastError) {
          // Might be a network error - try refreshing token once
          try {
            this.oauthKey = await this.refreshManager.refreshToken('hubspot', this.oauthKey);
            this.updateOAuthKey(this.oauthKey);
          } catch (refreshError) {
            // Refresh failed, throw original error
            throw error;
          }
          retries++;
          continue;
        }

        // All retries exhausted or not a refresh issue
        throw error;
      }
    }

    throw lastError || new Error('HubSpot API request failed');
  }

  /**
   * Check if HubSpot response indicates OAuth refresh is needed
   * @private
   * @param {Object} response - HTTP response object
   * @returns {boolean} True if refresh is needed
   */
  _checkHubSpotError(response) {
    if (!response || !response.data) {
      return false;
    }

    const data = response.data;
    
    // Check for HubSpot-specific error codes (case-insensitive status check)
    const status = (data.status || '').toLowerCase();
    if (status === 'error') {
      const message = (data.message || '').toLowerCase();
      const category = data.category || '';
      
      // HubSpot error codes that indicate token refresh needed
      const refreshErrorCodes = [
        'INVALID_AUTHENTICATION',
        'EXPIRED_AUTHENTICATION',
        'TOKEN_EXPIRED',
        'REFRESH_TOKEN_EXPIRED',
        'INVALID_REFRESH_TOKEN'
      ];

      // Check error category (case-sensitive as HubSpot uses uppercase)
      if (refreshErrorCodes.includes(category)) {
        return true;
      }

      // Check message for token-related errors (case-insensitive)
      if (message.includes('token') || 
          message.includes('authentication') || 
          message.includes('unauthorized') ||
          message.includes('expired')) {
        return true;
      }
    }

    // Check for JSON error objects
    if (data.error) {
      const errorCode = data.error.code || data.error.message || '';
      if (typeof errorCode === 'string') {
        const lowerError = errorCode.toLowerCase();
        if (lowerError.includes('token') || 
            lowerError.includes('auth') || 
            lowerError.includes('unauthorized') ||
            lowerError.includes('expired')) {
          return true;
        }
      }
    }

    return false;
  }

  /**
   * Extract error message from HubSpot API response
   * @private
   * @param {Object} response - HTTP response object
   * @returns {string} Error message
   */
  _extractErrorMessage(response) {
    if (!response.data) {
      return response.statusText || 'Unknown error';
    }

    const data = response.data;

    // HubSpot error format (case-insensitive status check)
    const status = (data.status || '').toLowerCase();
    if (status === 'error' && data.message) {
      return data.message;
    }

    // Standard error object
    if (data.error) {
      if (typeof data.error === 'string') {
        return data.error;
      }
      if (data.error.message) {
        return data.error.message;
      }
    }

    // Fallback
    return JSON.stringify(data);
  }

  /**
   * Convenience methods for common operations
   */

  /**
   * GET request
   * @param {string} url - API endpoint
   * @param {Object} params - Query parameters
   * @param {Object} options - Additional request options
   */
  async get(url, params = {}, options = {}) {
    return this.request('GET', url, { params, ...options });
  }

  /**
   * POST request
   * @param {string} url - API endpoint
   * @param {Object} data - Request body
   * @param {Object} options - Additional request options
   */
  async post(url, data = {}, options = {}) {
    return this.request('POST', url, { data, ...options });
  }

  /**
   * PATCH request
   * @param {string} url - API endpoint
   * @param {Object} data - Request body
   * @param {Object} options - Additional request options
   */
  async patch(url, data = {}, options = {}) {
    return this.request('PATCH', url, { data, ...options });
  }

  /**
   * PUT request
   * @param {string} url - API endpoint
   * @param {Object} data - Request body
   * @param {Object} options - Additional request options
   */
  async put(url, data = {}, options = {}) {
    return this.request('PUT', url, { data, ...options });
  }

  /**
   * DELETE request
   * @param {string} url - API endpoint
   * @param {Object} options - Additional request options
   */
  async delete(url, options = {}) {
    return this.request('DELETE', url, options);
  }
}

