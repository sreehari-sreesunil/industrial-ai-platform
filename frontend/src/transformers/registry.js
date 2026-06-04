import { createOrganization } from '../types/organization.js';
import { createFacility } from '../types/facility.js';
import { createAssetType } from '../types/assetType.js';
import { createMetricDefinition } from '../types/metricDefinition.js';

export function mapOrganization(raw) {
  if (!raw) return null;
  return createOrganization(raw);
}

export function mapOrganizationList(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(mapOrganization).filter(Boolean);
}

export function mapFacility(raw) {
  if (!raw) return null;
  return createFacility(raw);
}

export function mapFacilityList(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(mapFacility).filter(Boolean);
}

export function mapAssetType(raw) {
  if (!raw) return null;
  return createAssetType(raw);
}

export function mapAssetTypeList(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(mapAssetType).filter(Boolean);
}

export function mapMetricDefinition(raw) {
  if (!raw) return null;
  return createMetricDefinition(raw);
}

export function mapMetricDefinitionList(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(mapMetricDefinition).filter(Boolean);
}
