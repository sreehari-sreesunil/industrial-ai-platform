import { createTelemetry } from '../types/telemetry.js';

/**
 * Maps a raw backend telemetry record to a normalized Telemetry object.
 * @param {Object} raw
 * @returns {Telemetry}
 */
export function mapTelemetry(raw) {
  if (!raw) return null;
  return createTelemetry(raw);
}

/**
 * Maps a list of raw backend telemetry records.
 * @param {Array<Object>} rawList
 * @returns {Array<Telemetry>}
 */
export function mapTelemetryList(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(mapTelemetry).filter(Boolean);
}
