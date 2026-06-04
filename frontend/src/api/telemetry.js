import client from './client.js';
import { mapTelemetry, mapTelemetryList } from '../transformers/telemetry.js';

/**
 * Ingests a new telemetry data point.
 * @param {Object} data
 * @param {number|string} data.asset_id
 * @param {string} data.timestamp - ISO timestamp
 * @param {Object} data.payload - Key value pairs matching metric definitions
 * @returns {Promise<Telemetry>}
 */
export async function ingestTelemetry(data) {
  const response = await client.post('/telemetry/ingest', data);
  return mapTelemetry(response.data);
}

/**
 * Gets telemetry history for an asset.
 * @param {number|string} assetId
 * @param {string} [startTime]
 * @param {string} [endTime]
 * @returns {Promise<Array<Telemetry>>}
 */
export async function getTelemetryHistory(assetId, startTime, endTime) {
  const params = {};
  if (startTime) params.start_time = startTime;
  if (endTime) params.end_time = endTime;
  
  const response = await client.get(`/telemetry/assets/${assetId}`, { params });
  return mapTelemetryList(response.data);
}

/**
 * Gets the latest telemetry record for an asset. Returns null if 404 (no telemetry yet).
 * @param {number|string} assetId
 * @returns {Promise<Telemetry|null>}
 */
export async function getLatestTelemetry(assetId) {
  try {
    const response = await client.get(`/telemetry/assets/${assetId}/latest`);
    return mapTelemetry(response.data);
  } catch (error) {
    // If it's a 404, it means no telemetry has been ingested yet.
    if (error.response && error.response.status === 404) {
      return null;
    }
    throw error;
  }
}

/**
 * Gets telemetry statistics for a specific metric on an asset.
 * @param {number|string} assetId
 * @param {string} metric
 * @returns {Promise<{metric: string, avg: number, min: number, max: number, count: number}>}
 */
export async function getTelemetryStats(assetId, metric) {
  const response = await client.get(`/telemetry/assets/${assetId}/stats`, {
    params: { metric }
  });
  return response.data;
}

/**
 * Uploads telemetry CSV file.
 * @param {File} file
 * @returns {Promise<Object>}
 */
export async function uploadTelemetryCSV(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await client.post('/csv/telemetry-upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}
