import client from './client.js';
import {
  mapOrganization,
  mapOrganizationList,
  mapFacility,
  mapFacilityList,
  mapAssetType,
  mapAssetTypeList,
  mapMetricDefinition,
  mapMetricDefinitionList,
} from '../transformers/registry.js';

// Organizations
export async function getOrganizations() {
  const response = await client.get('/organizations');
  return mapOrganizationList(response.data);
}

export async function createOrganization(orgData) {
  const response = await client.post('/organizations', orgData);
  return mapOrganization(response.data);
}

// Facilities
export async function getFacilities() {
  const response = await client.get('/facilities');
  return mapFacilityList(response.data);
}

export async function createFacility(facilityData) {
  const response = await client.post('/facilities', facilityData);
  return mapFacility(response.data);
}

// Asset Types
export async function getAssetTypes() {
  const response = await client.get('/asset-types');
  return mapAssetTypeList(response.data);
}

export async function createAssetType(assetTypeData) {
  const response = await client.post('/asset-types', assetTypeData);
  return mapAssetType(response.data);
}

// Metric Definitions
export async function getMetricDefinitions(assetTypeId) {
  const params = {};
  if (assetTypeId) {
    params.asset_type_id = assetTypeId;
  }
  const response = await client.get('/metric-definitions', { params });
  return mapMetricDefinitionList(response.data);
}

export async function createMetricDefinition(metricData) {
  const response = await client.post('/metric-definitions', metricData);
  return mapMetricDefinition(response.data);
}
