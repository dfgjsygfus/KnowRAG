import assert from "node:assert/strict";
import test from "node:test";

import { backendUrl } from "./backendUrl.js";

test("backendUrl joins paths without duplicate slashes", () => {
  assert.equal(backendUrl("/api/chat/stream", "http://localhost:9000/"), "http://localhost:9000/api/chat/stream");
});
