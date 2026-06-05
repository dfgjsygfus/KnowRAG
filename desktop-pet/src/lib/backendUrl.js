const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export const API_BASE_URL = normalizeBaseUrl(import.meta.env?.VITE_API_BASE_URL || DEFAULT_BACKEND_URL);

export function backendUrl(path, baseUrl = API_BASE_URL) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizeBaseUrl(baseUrl)}${normalizedPath}`;
}

function normalizeBaseUrl(baseUrl) {
  return baseUrl.replace(/\/+$/, "");
}
