import assert from "node:assert/strict";
import test from "node:test";

import { useAdminApi } from "../composables/useAdminApi.js";

const originalFetch = global.fetch;

test("useAdminApi fetchDocuments calls /api/documents", async () => {
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      json: async () => ({ documents: [] }),
    };
  };

  const api = useAdminApi();
  const result = await api.fetchDocuments();

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://127.0.0.1:8000/api/documents");
  assert.equal(calls[0].options.method, undefined);
  assert.deepEqual(result, { documents: [] });

  global.fetch = originalFetch;
});

test("useAdminApi uploadDocument serializes payload", async () => {
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      json: async () => ({ id: 1 }),
    };
  };

  const api = useAdminApi();
  const payload = { filename: "a.md", content: "# Hello", size: 12 };
  await api.uploadDocument(payload);

  assert.equal(calls[0].url, "http://127.0.0.1:8000/api/documents/upload");
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.body, JSON.stringify(payload));
  assert.equal(calls[0].options.headers["Content-Type"], "application/json");

  global.fetch = originalFetch;
});

test("useAdminApi throws on error response", async () => {
  global.fetch = async () => ({
    ok: false,
    status: 502,
    json: async () => ({ detail: "Milvus unavailable" }),
  });

  const api = useAdminApi();
  await assert.rejects(api.fetchDocuments(), /Milvus unavailable/);

  global.fetch = originalFetch;
});
