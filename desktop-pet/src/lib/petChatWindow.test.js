import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  PET_CHAT_WINDOW_HEIGHT,
  PET_CHAT_WINDOW_LABEL,
  PET_CHAT_WINDOW_WIDTH,
  createPetChatWindowUrl,
  getPetChatWindowPosition,
  getPetChatWindowPositionFromPetRect,
  openPetChatWindow,
  positionPetChatWindow,
} from "./petChatWindow.js";

const defaultCapability = JSON.parse(
  readFileSync(new URL("../../src-tauri/capabilities/default.json", import.meta.url), "utf8"),
);

test("getPetChatWindowPosition anchors the input window below the pet", () => {
  assert.deepEqual(
    getPetChatWindowPosition(
      { x: 100, y: 200 },
      { x: 76, y: 94 },
      116,
    ),
    { x: 26, y: 360 },
  );
});

test("getPetChatWindowPositionFromPetRect uses the real pet DOM rect in large transparent windows", () => {
  assert.deepEqual(
    getPetChatWindowPositionFromPetRect(
      { x: 0, y: 0 },
      { left: 1600, top: 72, width: 80, height: 80, right: 1680, bottom: 152 },
    ),
    { x: 1490, y: 160 },
  );
});

test("getPetChatWindowPositionFromPetRect stays close to the pet inside large transparent windows", () => {
  assert.deepEqual(
    getPetChatWindowPositionFromPetRect(
      { x: 100, y: 200 },
      { left: 18, top: 54, width: 80, height: 80, right: 98, bottom: 134 },
      { width: 152, height: 188 },
    ),
    { x: 8, y: 342 },
  );
});

test("createPetChatWindowUrl routes to the standalone chat input view", () => {
  assert.equal(createPetChatWindowUrl(), "/?view=pet-chat");
});

test("default Tauri capability grants permissions to standalone pet windows", () => {
  assert.ok(defaultCapability.windows.includes("main"));
  assert.ok(defaultCapability.windows.includes(PET_CHAT_WINDOW_LABEL));
  assert.ok(defaultCapability.windows.includes("pet-context-menu"));
});

test("openPetChatWindow waits for first-time window creation before native operations", async () => {
  const calls = [];
  const handlers = {};

  const currentWindow = {
    async scaleFactor() {
      return 1;
    },
    async outerPosition() {
      return { toLogical: () => ({ x: 100, y: 200 }) };
    },
    async outerSize() {
      return { toLogical: () => ({ width: 152, height: 188 }) };
    },
  };

  class FakeWebviewWindow {
    static async getByLabel(label) {
      calls.push(["getByLabel", label]);
      return null;
    }

    constructor(label, options) {
      this.label = label;
      this.options = options;
      calls.push(["create", label, options]);
    }

    async once(event, handler) {
      handlers[event] = handler;
      calls.push(["once", event]);
      return () => {};
    }

    async setSize(size) {
      calls.push(["setSize", size.width, size.height]);
    }

    async setPosition(position) {
      calls.push(["setPosition", position.x, position.y]);
    }

    async show() {
      calls.push(["show"]);
    }

    async setFocus() {
      calls.push(["setFocus"]);
    }
  }

  const opening = openPetChatWindow({
    WebviewWindowClass: FakeWebviewWindow,
    currentWindow,
    petScale: 1,
  });

  for (let i = 0; i < 10 && !handlers["tauri://created"]; i += 1) {
    await Promise.resolve();
  }
  assert.equal(typeof handlers["tauri://created"], "function");
  assert.deepEqual(
    calls.filter(([name]) => ["setSize", "setPosition", "show", "setFocus"].includes(name)),
    [],
  );

  handlers["tauri://created"]();
  await opening;

  assert.deepEqual(calls.slice(-4), [
    ["setSize", PET_CHAT_WINDOW_WIDTH, PET_CHAT_WINDOW_HEIGHT],
    ["setPosition", 26, 360],
    ["show"],
    ["setFocus"],
  ]);
});

test("positionPetChatWindow can bring an existing input window to front after moving", async () => {
  const calls = [];
  const existingWindow = {
    async setSize(size) {
      calls.push(["setSize", size.width, size.height]);
    },
    async setPosition(position) {
      calls.push(["setPosition", position.x, position.y]);
    },
    async show() {
      calls.push(["show"]);
    },
    async setFocus() {
      calls.push(["setFocus"]);
    },
  };

  const currentWindow = {
    async scaleFactor() {
      return 1;
    },
    async outerPosition() {
      return { toLogical: () => ({ x: 120, y: 240 }) };
    },
    async outerSize() {
      return { toLogical: () => ({ width: 152, height: 188 }) };
    },
  };

  class FakeWebviewWindow {
    static async getByLabel(label) {
      calls.push(["getByLabel", label]);
      return existingWindow;
    }
  }

  await positionPetChatWindow({
    WebviewWindowClass: FakeWebviewWindow,
    currentWindow,
    petScale: 1,
    petBounds: { left: 18, top: 54, width: 80, height: 80, right: 98, bottom: 134 },
    bringToFront: true,
  });

  assert.deepEqual(calls, [
    ["getByLabel", PET_CHAT_WINDOW_LABEL],
    ["setSize", PET_CHAT_WINDOW_WIDTH, PET_CHAT_WINDOW_HEIGHT],
    ["setPosition", 28, 382],
    ["show"],
    ["setFocus"],
  ]);
});

test("openPetChatWindow creates a hidden standalone transparent input window before showing it", async () => {
  const calls = [];
  let createdWindow = null;

  const currentWindow = {
    async scaleFactor() {
      return 1;
    },
    async outerPosition() {
      return { toLogical: () => ({ x: 100, y: 200 }) };
    },
    async outerSize() {
      return { toLogical: () => ({ width: 152, height: 188 }) };
    },
  };

  class FakeWebviewWindow {
    static async getByLabel(label) {
      calls.push(["getByLabel", label]);
      return null;
    }

    constructor(label, options) {
      this.label = label;
      this.options = options;
      createdWindow = this;
      calls.push(["create", label, options]);
    }

    async once(event, handler) {
      calls.push(["once", event]);
      if (event === "tauri://created") handler();
      return () => {};
    }

    async setSize(size) {
      calls.push(["setSize", size.width, size.height]);
    }

    async setPosition(position) {
      calls.push(["setPosition", position.x, position.y]);
    }

    async show() {
      calls.push(["show"]);
    }

    async setFocus() {
      calls.push(["setFocus"]);
    }
  }

  await openPetChatWindow({
    WebviewWindowClass: FakeWebviewWindow,
    currentWindow,
    petScale: 1,
    petBounds: { left: 1600, top: 72, width: 80, height: 80, right: 1680, bottom: 152 },
  });

  assert.equal(createdWindow.label, PET_CHAT_WINDOW_LABEL);
  assert.equal(createdWindow.options.url, createPetChatWindowUrl());
  assert.equal(createdWindow.options.width, PET_CHAT_WINDOW_WIDTH);
  assert.equal(createdWindow.options.height, PET_CHAT_WINDOW_HEIGHT);
  assert.equal(createdWindow.options.visible, false);
  assert.equal(createdWindow.options.transparent, true);
  assert.deepEqual(calls.slice(-4), [
    ["setSize", PET_CHAT_WINDOW_WIDTH, PET_CHAT_WINDOW_HEIGHT],
    ["setPosition", 1590, 360],
    ["show"],
    ["setFocus"],
  ]);
});
