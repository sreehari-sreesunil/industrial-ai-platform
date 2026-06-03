import { apiClient } from "./client";

export async function getAssets() {
  const response = await apiClient.get("/assets");

  return response.data;
}

export async function getAssetById(id) {
  const response = await apiClient.get(`/assets/${id}`);

  return response.data;
}