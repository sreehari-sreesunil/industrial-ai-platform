import client from './client.js';
import { mapAsset, mapAssetList } from '../transformers/asset.js';

/**
 * Fetches all assets from the backend and maps them.
 * @returns {Promise<Array<Asset>>}
 */
export async function getAssets() {
  const response = await client.get('/assets');
  return mapAssetList(response.data);
}

/**
 * Creates a new asset on the backend.
 * @param {Object} assetData
 * @param {string} assetData.name
 * @param {number|string} assetData.facility_id
 * @param {number|string} assetData.asset_type_id
 * @returns {Promise<Asset>}
 */
export async function createAsset(assetData) {
  const response = await client.post('/assets', assetData);
  return mapAsset(response.data);
}
