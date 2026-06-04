/**
 * @typedef {Object} AssetType
 * @property {number|string} id
 * @property {string} name
 * @property {string} description
 */

/**
 * Creates a normalized AssetType object
 * @param {Object} raw
 * @returns {AssetType}
 */
export function createAssetType(raw = {}) {
  return {
    id: raw.id || '',
    name: raw.name || '',
    description: raw.description || '',
  };
}
