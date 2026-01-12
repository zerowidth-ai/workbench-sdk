/**
 * Cache management utilities for the zv1 engine
 * Provides a consistent interface for reading and writing cache values
 * Making it easy to change cache structure/format without modifying core logic
 * 
 * Cache Structure:
 * Each cache key stores an ARRAY of OBJECTS with value + metadata:
 * [
 *   { value: "hello", timestamp: 1234567890 },
 *   { value: "world", timestamp: 1234567891 }
 * ]
 * 
 * This enables:
 * - Value history tracking
 * - Refiring input support (consume only NEW values)
 * - Non-refiring inputs (always use latest, can reuse consumed values)
 * - Debugging and time-travel
 * 
 * Consumption Tracking:
 * Tracked per-node, per-input in node.settings._consumption_tracking
 * Only used for refiring inputs - non-refiring inputs ignore it
 */

/**
 * CacheManager - Manages the execution cache for node outputs
 * Uses an array-based store where each key maps to an array of value entries
 * Each entry is { value, timestamp }
 * - set() appends new entry with current timestamp
 * - get() returns the most recent value
 * - getNew() returns values newer than a timestamp (for refiring)
 */
export class CacheManager {
  constructor() {
    this._store = {};
  }

  /**
   * Generate a cache key from node_id and port_name
   * @private
   * @param {string} node_id - The node ID
   * @param {string} port_name - The port/output name
   * @returns {string} The cache key
   */
  _generateKey(node_id, port_name) {
    return `${node_id}:${port_name}`;
  }

  /**
   * Ensure a key exists in the store with an empty array
   * @private
   * @param {string} key - The cache key
   */
  _ensureKey(key) {
    if (!(key in this._store)) {
      this._store[key] = [];
    }
  }

  /**
   * Set a value in the cache (appends to the value array with timestamp)
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @param {any} params.value - The value to store
   */
  set({ node_id, port_name, value }) {
    const key = this._generateKey(node_id, port_name);
    this._ensureKey(key);

    // console.log('setting:', 'node_id', node_id, 'port_name', port_name, 'value', value);
    this._store[key].push({
      value,
      timestamp: Number(process.hrtime.bigint()) // High-resolution timestamp in nanoseconds
    });
  }

  /**
   * Get the most recent value from the cache
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @returns {any} The most recent cached value, or undefined if not found
   */
  get({ node_id, port_name }) {
    const key = this._generateKey(node_id, port_name);
    const entries = this._store[key];

    // console.log('getting:', 'node_id', node_id, 'port_name', port_name, 'entries', JSON.stringify(entries));
    if (!entries || entries.length === 0) {
      return undefined;
    }
    return entries[entries.length - 1].value;
  }

  /**
   * Get the most recent entry (with metadata) from the cache
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @returns {Object|undefined} The most recent entry { value, timestamp }, or undefined if not found
   */
  getEntry({ node_id, port_name }) {
    const key = this._generateKey(node_id, port_name);
    const entries = this._store[key];
    if (!entries || entries.length === 0) {
      return undefined;
    }
    return entries[entries.length - 1];
  }

  /**
   * Get new values that arrived after a specific timestamp (for refiring inputs)
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @param {number} params.afterTimestamp - Only return values newer than this timestamp
   * @returns {Array} Array of values that are newer than the timestamp
   */
  getNew({ node_id, port_name, afterTimestamp }) {
    const key = this._generateKey(node_id, port_name);
    const entries = this._store[key];
    if (!entries || entries.length === 0) {
      return [];
    }
    
    const newEntries = entries.filter(entry => entry.timestamp > afterTimestamp);
    return newEntries.map(entry => entry.value);
  }

  /**
   * Get the timestamp of the most recent value
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @returns {number|undefined} The timestamp of the most recent value, or undefined if not found
   */
  getLatestTimestamp({ node_id, port_name }) {
    const key = this._generateKey(node_id, port_name);
    const entries = this._store[key];
    if (!entries || entries.length === 0) {
      return undefined;
    }
    return entries[entries.length - 1].timestamp;
  }

  /**
   * Check if a value exists in the cache
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @returns {boolean} True if the key exists and has at least one value
   */
  has({ node_id, port_name }) {
    const key = this._generateKey(node_id, port_name);
    const entries = this._store[key];
    return entries && entries.length > 0;
  }

  /**
   * Check if there are new values after a specific timestamp (for refiring)
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @param {number} params.afterTimestamp - Check for values newer than this timestamp
   * @returns {boolean} True if there are values newer than the timestamp
   */
  hasNew({ node_id, port_name, afterTimestamp }) {
    const key = this._generateKey(node_id, port_name);
    const entries = this._store[key];
    if (!entries || entries.length === 0) {
      return false;
    }
    return entries.some(entry => entry.timestamp > afterTimestamp);
  }

  /**
   * Delete a value from the cache (clears the array and removes the key)
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @returns {boolean} True if the key existed and was deleted
   */
  delete({ node_id, port_name }) {
    const key = this._generateKey(node_id, port_name);
    if (key in this._store) {
      delete this._store[key];
      return true;
    }
    return false;
  }

  /**
   * Clear all values from the cache
   */
  clear() {
    this._store = {};
  }

  /**
   * Get all cache entries for a specific node (most recent values only)
   * @param {string} node_id - The node ID
   * @returns {Object} Object with port_name keys and their most recent values
   */
  getNodeOutputs(node_id) {
    const outputs = {};
    const prefix = `${node_id}:`;
    
    for (const key in this._store) {
      if (key.startsWith(prefix)) {
        const port_name = key.slice(prefix.length);
        const entries = this._store[key];
        if (entries && entries.length > 0) {
          outputs[port_name] = entries[entries.length - 1].value;
        }
      }
    }
    
    return outputs;
  }

  /**
   * Get the full history of values for a specific cache entry
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @returns {Array} Array of all values (oldest to newest), empty array if not found
   */
  getHistory({ node_id, port_name }) {
    const key = this._generateKey(node_id, port_name);
    const entries = this._store[key];
    return entries ? entries.map(entry => entry.value) : [];
  }

  /**
   * Get the full history with metadata for a specific cache entry
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @returns {Array} Array of all entries { value, timestamp } (oldest to newest), empty array if not found
   */
  getHistoryWithMetadata({ node_id, port_name }) {
    const key = this._generateKey(node_id, port_name);
    const entries = this._store[key];
    return entries ? [...entries] : [];
  }

  /**
   * Get all values (history) for all outputs of a specific node
   * @param {string} node_id - The node ID
   * @returns {Object} Object with port_name keys and their full history arrays
   */
  getNodeHistory(node_id) {
    const history = {};
    const prefix = `${node_id}:`;
    
    for (const key in this._store) {
      if (key.startsWith(prefix)) {
        const port_name = key.slice(prefix.length);
        history[port_name] = this._store[key].map(entry => entry.value);
      }
    }
    
    return history;
  }

  /**
   * Pop the most recent value from the cache (removes and returns it)
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @returns {any} The most recent value, or undefined if not found
   */
  pop({ node_id, port_name }) {
    const key = this._generateKey(node_id, port_name);
    const entries = this._store[key];
    if (!entries || entries.length === 0) {
      return undefined;
    }
    const entry = entries.pop();
    return entry.value;
  }

  /**
   * Get the number of values stored for a specific cache entry
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @returns {number} Number of values in the history
   */
  getHistoryLength({ node_id, port_name }) {
    const key = this._generateKey(node_id, port_name);
    const entries = this._store[key];
    return entries ? entries.length : 0;
  }

  /**
   * Get the raw cache key (for legacy compatibility)
   * @param {Object} params - Parameters object
   * @param {string} params.node_id - The node ID
   * @param {string} params.port_name - The port/output name
   * @returns {string} The cache key
   */
  getKey({ node_id, port_name }) {
    return this._generateKey(node_id, port_name);
  }

  /**
   * Get access to the underlying store (use sparingly)
   * Note: Store structure is { key: [value1, value2, ...] }
   * @returns {Object} The cache store with array values
   */
  getRawStore() {
    return this._store;
  }

  /**
   * Get all cache keys
   * @returns {string[]} Array of all cache keys
   */
  getAllKeys() {
    return Object.keys(this._store);
  }

  /**
   * Get statistics about the cache
   * @returns {Object} Cache statistics including total keys, total entries, and average history length
   */
  getStats() {
    const keys = Object.keys(this._store);
    const totalKeys = keys.length;
    let totalEntries = 0;
    
    for (const key of keys) {
      totalEntries += this._store[key].length;
    }
    
    return {
      totalKeys,
      totalEntries,
      averageHistoryLength: totalKeys > 0 ? (totalEntries / totalKeys).toFixed(2) : 0
    };
  }

  /**
   * Helper to get consumption tracking for a node
   * @param {Object} nodeSettings - The node's settings object
   * @returns {Object} The consumption tracking object (or empty if not exists)
   */
  static getConsumptionTracking(nodeSettings) {
    return nodeSettings?._consumption_tracking || {};
  }

  /**
   * Helper to update consumption tracking for a node input
   * @param {Object} nodeSettings - The node's settings object
   * @param {string} inputName - The input port name
   * @param {number} timestamp - The timestamp to mark as consumed
   * @returns {Object} Updated settings object with new consumption tracking
   */
  static updateConsumptionTracking(nodeSettings, inputName, timestamp) {
    return {
      _consumption_tracking: {
        ...(nodeSettings?._consumption_tracking || {}),
        [inputName]: timestamp
      }
    };
  }

  /**
   * Helper to get the last consumed timestamp for a specific input
   * @param {Object} nodeSettings - The node's settings object
   * @param {string} inputName - The input port name
   * @returns {number} The last consumed timestamp, or 0 if never consumed
   */
  static getLastConsumed(nodeSettings, inputName) {
    return nodeSettings?._consumption_tracking?.[inputName] || 0;
  }
}

export default CacheManager;

