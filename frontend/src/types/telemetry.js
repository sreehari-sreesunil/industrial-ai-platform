/**
 * @typedef {Object} Telemetry
 * @property {number|string} id
 * @property {number|string} assetId
 * @property {string} timestamp
 * @property {Record<string, number|string|boolean>} payload
 */

/**
 * Creates a normalized Telemetry object
 * @param {Object} raw
 * @returns {Telemetry}
 */
export function createTelemetry(raw = {}) {
  return {
    id: raw.id || '',
    assetId: raw.asset_id || '',
    timestamp: raw.timestamp || '',
    payload: raw.payload || {},
  };
}
