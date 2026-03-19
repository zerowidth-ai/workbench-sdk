/**
 * Sanitize an API call event by stripping auth credentials from headers and URLs.
 *
 * @param {Object} event - Raw API call event
 * @returns {Object} Sanitized event safe for user consumption
 */
export function sanitizeAPICallEvent(event) {
    const sanitized = { ...event };

    if (sanitized.request) {
        sanitized.request = { ...sanitized.request };

        // Sanitize headers - redact auth-related values
        if (sanitized.request.headers) {
            const authPattern = /^(authorization|x-api-key|api-key|apikey|cookie)$/i;
            const cleanHeaders = {};
            for (const [key, value] of Object.entries(sanitized.request.headers)) {
                cleanHeaders[key] = authPattern.test(key) ? '[REDACTED]' : value;
            }
            sanitized.request.headers = cleanHeaders;
        }

        // Sanitize URL query params - redact sensitive values
        if (sanitized.request.url) {
            try {
                const urlObj = new URL(sanitized.request.url);
                const sensitiveParams = /^(key|apikey|api_key|token|secret|password|access_token)$/i;
                for (const key of [...urlObj.searchParams.keys()]) {
                    if (sensitiveParams.test(key)) {
                        urlObj.searchParams.set(key, '[REDACTED]');
                    }
                }
                sanitized.request.url = urlObj.toString();
            } catch (e) {
                // If URL parsing fails, leave as-is
            }
        }
    }

    return sanitized;
}

/**
 * Emit an onAPICall event if the callback is configured.
 * Handles both sync and async callbacks and swallows callback errors.
 *
 * @param {Object} engineConfig - Engine config (may contain onAPICall)
 * @param {Object} rawEvent - Raw unsanitized event data
 */
export async function emitAPICallEvent(engineConfig, rawEvent) {
    if (!engineConfig?.onAPICall) return;

    const event = sanitizeAPICallEvent(rawEvent);

    try {
        const result = engineConfig.onAPICall(event);
        if (result && typeof result.then === 'function') {
            await result;
        }
    } catch (e) {
        // Don't let callback errors break the integration
    }
}
