import { backendUrl } from "../lib/backendUrl.js";

const DEFAULT_TIMEOUT_MS = 30000;

export function useAdminApi() {
  async function apiFetch(path, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), options.timeoutMs || DEFAULT_TIMEOUT_MS);

    try {
      const response = await fetch(backendUrl(path), {
        ...options,
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        signal: controller.signal,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || `HTTP ${response.status}`);
      }
      return body;
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("请求超时，请检查后端服务");
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  return {
    fetchDocuments: () => apiFetch("/api/documents"),
    uploadDocument: (payload) =>
      apiFetch("/api/documents/upload", { method: "POST", body: JSON.stringify(payload) }),
    fetchDocument: (id) => apiFetch(`/api/documents/${id}`),
    indexDocument: (id) => apiFetch(`/api/documents/${id}/index`, { method: "POST" }),
    deleteDocument: (id) => apiFetch(`/api/documents/${id}`, { method: "DELETE" }),
    fetchChatModelSettings: () => apiFetch("/api/settings/chat-model"),
    updateChatModelSettings: (payload) =>
      apiFetch("/api/settings/chat-model", { method: "PUT", body: JSON.stringify(payload) }),
    testChatModelConnection: (payload) =>
      apiFetch("/api/settings/chat-model/test", { method: "POST", body: JSON.stringify(payload) }),
  };
}
