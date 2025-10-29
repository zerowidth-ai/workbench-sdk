/**
 * OAuth 2.0 Token Refresh Utility
 * 
 * Handles OAuth token refresh with:
 * - Expiry pre-checking (epoch or ISO timestamps)
 * - Refresh coalescing (multiple nodes waiting for same provider refresh)
 * - Retry logic with max retries
 * - Automatic in-memory key updates
 */

/**
 * Check if a key is an OAuth key (has accessToken and onRefresh)
 * @param {any} key - The key value to check
 * @returns {boolean} True if this is an OAuth key
 */
export function isOAuthKey(key) {
  return (
    key &&
    typeof key === 'object' &&
    (typeof key.accessToken === 'string' || typeof key.access_token === 'string') &&
    typeof key.onRefresh === 'function'
  );
}

/**
 * Parse expiresAt value (supports epoch milliseconds or ISO string)
 * @param {number|string|undefined} expiresAt - Expiry timestamp
 * @returns {number|null} Milliseconds since epoch, or null if invalid/undefined
 */
export function parseExpiresAt(expiresAt) {
  if (!expiresAt) return null;
  
  if (typeof expiresAt === 'number') {
    return expiresAt;
  }
  
  if (typeof expiresAt === 'string') {
    // Try ISO string
    const isoDate = new Date(expiresAt);
    if (!isNaN(isoDate.getTime())) {
      return isoDate.getTime();
    }
    
    // Try epoch string
    const epochNum = parseInt(expiresAt, 10);
    if (!isNaN(epochNum)) {
      return epochNum;
    }
  }
  
  return null;
}

/**
 * Check if token is expired or will expire soon
 * @param {Object} oauthKey - OAuth key object
 * @param {number} expirySkewMs - Milliseconds before actual expiry to consider expired
 * @returns {boolean} True if token needs refresh
 */
export function isTokenExpired(oauthKey, expirySkewMs = 0) {
  const expiresAt = parseExpiresAt(oauthKey.expiresAt);
  if (!expiresAt) {
    // No expiry info - assume not expired (can't determine)
    return false;
  }
  
  const now = Date.now();
  const expiryThreshold = expiresAt - expirySkewMs;
  return now >= expiryThreshold;
}

/**
 * OAuth Refresh Manager
 * Handles token refresh with coalescing for concurrent requests
 */
export class OAuthRefreshManager {
  constructor(config = {}) {
    // Map of provider -> refresh promise (for coalescing)
    this.refreshPromises = new Map();
    
    // Configuration
    this.expirySkewMs = config.oauthExpirySkewMs || 60000; // Default: 1 minute
    this.maxRefreshRetries = config.oauthMaxRefreshRetries || 3;
    this.refreshTimeoutMs = config.oauthRefreshTimeoutMs || 20000; // Default: 20 seconds
    this.onNodeUpdate = config.onNodeUpdate || null;
    this.keys = config.keys || null; // Reference to keys object for updates
  }

  /**
   * Ensure token is valid, refresh if needed
   * @param {string} provider - Provider name (e.g., 'hubspot')
   * @param {Object} oauthKey - OAuth key object
   * @returns {Promise<Object>} Updated OAuth key object with valid token
   * @throws {Error} If refresh fails after max retries
   */
  async ensureValidToken(provider, oauthKey) {
    // Check if token is expired
    if (!isTokenExpired(oauthKey, this.expirySkewMs)) {
      return oauthKey;
    }

    // Token needs refresh
    return await this.refreshToken(provider, oauthKey);
  }

  /**
   * Refresh OAuth token with coalescing support
   * @param {string} provider - Provider name
   * @param {Object} oauthKey - OAuth key object
   * @returns {Promise<Object>} Updated OAuth key object
   * @throws {Error} If refresh fails after max retries
   */
  async refreshToken(provider, oauthKey) {
    // Check if refresh is already in progress for this provider
    const existingRefresh = this.refreshPromises.get(provider);
    if (existingRefresh) {
      // Wait for existing refresh to complete
      try {
        return await existingRefresh;
      } catch (error) {
        // If existing refresh failed, retry our own
        // Fall through to start new refresh
      }
    }

    // Start new refresh
    const refreshPromise = this._performRefresh(provider, oauthKey);
    this.refreshPromises.set(provider, refreshPromise);

    try {
      const updatedKey = await refreshPromise;
      return updatedKey;
    } finally {
      // Clean up promise after completion
      this.refreshPromises.delete(provider);
    }
  }

  /**
   * Perform the actual token refresh
   * @private
   * @param {string} provider - Provider name
   * @param {Object} oauthKey - OAuth key object
   * @returns {Promise<Object>} Updated OAuth key object
   */
  async _performRefresh(provider, oauthKey) {
    let lastError = null;
    let retries = 0;

    // Emit refresh started event
    if (this.onNodeUpdate) {
      this.onNodeUpdate({
        type: 'oauth_refresh_start',
        provider,
        timestamp: Date.now(),
        data: {
          status: 'started',
          retryAttempt: retries
        }
      });
    }

    while (retries <= this.maxRefreshRetries) {
      try {
        // Create timeout promise
        const timeoutPromise = new Promise((_, reject) => {
          setTimeout(() => {
            reject(new Error(`OAuth refresh timeout after ${this.refreshTimeoutMs}ms`));
          }, this.refreshTimeoutMs);
        });

        // Call onRefresh with timeout
        const refreshPromise = oauthKey.onRefresh({
          provider,
          currentToken: oauthKey.accessToken,
          refreshToken: oauthKey.refreshToken,
          expiresAt: oauthKey.expiresAt
        });

        const updatedKey = await Promise.race([refreshPromise, timeoutPromise]);

        // Validate the returned key object
        if (!updatedKey || typeof updatedKey !== 'object') {
          throw new Error('onRefresh callback must return an OAuth key object');
        }

        if (!updatedKey.accessToken || typeof updatedKey.accessToken !== 'string') {
          throw new Error('onRefresh callback must return an object with accessToken string');
        }

        // Update in-memory keys object
        if (this.keys && this.keys[provider]) {
          this.keys[provider] = { ...this.keys[provider], ...updatedKey };
        }

        // Emit refresh success event
        if (this.onNodeUpdate) {
          this.onNodeUpdate({
            type: 'oauth_refresh_complete',
            provider,
            timestamp: Date.now(),
            data: {
              status: 'success',
              retryAttempt: retries
            }
          });
        }

        return updatedKey;
      } catch (error) {
        lastError = error;
        retries++;

        // Emit refresh failure event (if not final attempt)
        if (retries <= this.maxRefreshRetries && this.onNodeUpdate) {
          this.onNodeUpdate({
            type: 'oauth_refresh_failed',
            provider,
            timestamp: Date.now(),
            data: {
              status: 'failed',
              retryAttempt: retries,
              error: error.message
            }
          });
        }

        // If we've exhausted retries, break
        if (retries > this.maxRefreshRetries) {
          break;
        }

        // Wait before retry (exponential backoff: 100ms, 200ms, 400ms)
        await new Promise(resolve => setTimeout(resolve, Math.min(100 * Math.pow(2, retries - 1), 1000)));
      }
    }

    // Emit final failure event
    if (this.onNodeUpdate) {
      this.onNodeUpdate({
        type: 'oauth_refresh_complete',
        provider,
        timestamp: Date.now(),
        data: {
          status: 'failed',
          retryAttempt: retries - 1,
          error: lastError?.message || 'Unknown error'
        }
      });
    }

    // All retries exhausted
    throw new Error(
      `OAuth refresh failed for provider '${provider}' after ${this.maxRefreshRetries} retries: ${lastError?.message || 'Unknown error'}`
    );
  }

  /**
   * Check if a response indicates token refresh is needed
   * @param {Object} response - HTTP response object (from axios)
   * @param {Function} providerSpecificCheck - Optional provider-specific check function
   * @returns {boolean} True if refresh is needed
   */
  static needsRefresh(response, providerSpecificCheck = null) {
    // Check HTTP status codes
    if (response && response.status) {
      if (response.status === 401 || response.status === 403) {
        return true;
      }
    }

    // Run provider-specific check if provided
    if (providerSpecificCheck) {
      return providerSpecificCheck(response);
    }

    return false;
  }
}

