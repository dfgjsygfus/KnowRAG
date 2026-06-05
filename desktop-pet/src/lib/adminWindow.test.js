import assert from "node:assert/strict";
import test from "node:test";

import { adminConsoleUrl, openAdminWindow } from "./adminWindow.js";

test("adminConsoleUrl uses the shared backend base URL", () => {
  assert.equal(adminConsoleUrl("http://localhost:9000/"), "http://localhost:9000/admin?v=3");
});

test("openAdminWindow creates the admin window when it does not exist", async () => {
  const created = [];
  class FakeWebviewWindow {
    static async getByLabel() {
      return null;
    }

    constructor(label, options) {
      created.push({ label, options });
    }
  }

  await openAdminWindow(FakeWebviewWindow);

  assert.equal(created.length, 1);
  assert.equal(created[0].label, "admin");
  assert.equal(created[0].options.url, "http://127.0.0.1:8000/admin?v=3");
});

test("openAdminWindow restores and focuses an existing admin window", async () => {
  const calls = [];
  const existingWindow = {
    async unminimize() {
      calls.push("unminimize");
    },
    async show() {
      calls.push("show");
    },
    async setFocus() {
      calls.push("focus");
    },
  };
  class FakeWebviewWindow {
    static async getByLabel() {
      return existingWindow;
    }

    constructor() {
      throw new Error("must not create a duplicate window");
    }
  }

  await openAdminWindow(FakeWebviewWindow);

  assert.deepEqual(calls, ["unminimize", "show", "focus"]);
});
