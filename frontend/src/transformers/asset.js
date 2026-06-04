import { createAsset } from '../types/asset.js';

/**
 * Maps a raw backend asset to a normalized Asset object.
 * @param {Object} raw
 * @returns {Asset}
 */
export function mapAsset(raw) {
  if (!raw) return null;
  return createAsset(raw);
}

/**
 * Maps a list of raw backend assets.
 * @param {Array<Object>} rawList
 * @returns {Array<Asset>}
 */
export function mapAssetList(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(mapAsset).filter(Boolean);
}
