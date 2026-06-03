import { apiClient } from "./client";

export async function getAssets() {
  const response = await apiClient.get("/assets");

  return response.data;
}