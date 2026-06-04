/**
 * @typedef {Object} NestedAssetType
 * @property {number|string} id
 * @property {string} name
 *
 * @typedef {Object} MetricDefinition
 * @property {number|string} id
 * @property {string} name
 * @property {string} unit
 * @property {string} dataType
 * @property {number|null} minValue
 * @property {number|null} maxValue
 * @property {NestedAssetType} assetType
 */

/**
 * Creates a normalized MetricDefinition object
 * @param {Object} raw
 * @returns {MetricDefinition}
 */
export function createMetricDefinition(raw = {}) {
  return {
    id: raw.id || '',
    name: raw.name || '',
    unit: raw.unit || '',
    dataType: raw.data_type || '',
    minValue: raw.min_value !== undefined ? raw.min_value : null,
    maxValue: raw.max_value !== undefined ? raw.max_value : null,
    assetType: {
      id: raw.asset_type?.id || '',
      name: raw.asset_type?.name || '',
    },
  };
}
