import assert from "node:assert/strict";
import test from "node:test";

import { exitDesktopPet } from "./appLifecycle.js";

test("exitDesktopPet closes every application window", async () => {
  const closed = [];
  const currentWindow = { label: "main", close: async () => closed.push("main") };
  const windows = [
    currentWindow,
    { label: "admin", close: async () => closed.push("admin") },
  ];

  await exitDesktopPet(async () => windows, currentWindow);

  assert.deepEqual(closed, ["admin", "main"]);
});
