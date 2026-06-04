/**
 * @typedef {Object} NestedFacility
 * @property {number|string} id
 * @property {string} name
 *
 * @typedef {Object} NestedAssetType
 * @property {number|string} id
 * @property {string} name
 *
 * @typedef {Object} Asset
 * @property {number|string} id
 * @property {string} name
 * @property {NestedFacility} facility
 * @property {NestedAssetType} assetType
 */

/**
 * Creates a normalized Asset object
 * @param {Object} raw
 * @returns {Asset}
 */
export function createAsset(raw = {}) {
  return {
    id: raw.id || '',
    name: raw.name || '',
    facility: {
      id: raw.facility?.id || '',
      name: raw.facility?.name || '',
    },
    assetType: {
      id: raw.asset_type?.id || '',
      name: raw.asset_type?.name || '',
    },
  };
}
