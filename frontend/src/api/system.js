import client from './client.js';
import { mapAssetList } from '../transformers/asset.js';

/**
 * Checks the backend health and returns status and latency.
 * @returns {Promise<{status: string, latency: number}>}
 */
export async function getHealth() {
  const start = performance.now();
  try {
    const response = await client.get('/health');
    const end = performance.now();
    return {
      status: response.data?.status || 'ok',
      latency: Math.round(end - start),
    };
  } catch (error) {
    const end = performance.now();
    return {
      status: 'offline',
      latency: Math.round(end - start),
    };
  }
}

/**
 * Checks backend liveness.
 * @returns {Promise<boolean>}
 */
export async function getLiveness() {
  try {
    const response = await client.get('/system/live');
    return response.data?.status === 'alive';
  } catch {
    return false;
  }
}

/**
 * Checks backend readiness.
 * @returns {Promise<boolean>}
 */
export async function getReadiness() {
  try {
    const response = await client.get('/system/ready');
    return response.data?.status === 'ready';
  } catch {
    return false;
  }
}

/**
 * Gets dashboard overview data.
 * @returns {Promise<Object>}
 */
export async function getDashboardOverview() {
  const response = await client.get('/dashboard/overview');
  const data = response.data;
  if (data && data.recent_assets) {
    data.recent_assets = mapAssetList(data.recent_assets);
  }
  return data;
}
