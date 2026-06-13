import assert from "node:assert/strict";
import test from "node:test";

import { createPetContextMenu, showPetContextMenu } from "./petContextMenu.js";

test("createPetContextMenu builds the native pet menu with chat and scale actions", async () => {
  const actions = [];
  const fakeMenu = { popup: async () => {} };
  class FakeMenu {
    static async new(options) {
      FakeMenu.options = options;
      return fakeMenu;
    }
  }

  const menu = await createPetContextMenu(
    FakeMenu,
    {
      openAdmin: () => actions.push("admin"),
      toggleChat: () => actions.push("toggle-chat"),
      openFull: () => actions.push("open-full"),
      setScale: (scale) => actions.push(`scale:${scale}`),
      exitPet: () => actions.push("exit"),
    },
    {
      chatSurface: "pet",
      petScale: 1.2,
    },
  );

  assert.equal(menu, fakeMenu);
  assert.deepEqual(
    FakeMenu.options.items.map((item) => item.text || item.item),
    ["打开管理台", "打开输入框", "打开完整聊天", "Separator", "调整大小", "Separator", "退出"],
  );

  const scaleSubmenu = FakeMenu.options.items[4];
  assert.deepEqual(
    scaleSubmenu.items.map((item) => item.text),
    ["小", "中", "大 ✓", "特大"],
  );

  FakeMenu.options.items[0].action();
  FakeMenu.options.items[1].action();
  FakeMenu.options.items[2].action();
  scaleSubmenu.items[2].action();
  FakeMenu.options.items[6].action();
  assert.deepEqual(actions, ["admin", "toggle-chat", "open-full", "scale:1.2", "exit"]);
});

test("createPetContextMenu reflects the current chat surface in the toggle label", async () => {
  class FakeMenu {
    static async new(options) {
      FakeMenu.options = options;
      return {};
    }
  }

  await createPetContextMenu(
    FakeMenu,
    {
      openAdmin: () => {},
      toggleChat: () => {},
      openFull: () => {},
      setScale: () => {},
      exitPet: () => {},
    },
    {
      chatSurface: "light",
      petScale: 1,
    },
  );

  assert.equal(FakeMenu.options.items[1].text, "关闭输入框");
});

test("showPetContextMenu delegates to the native popup API", async () => {
  const calls = [];
  const menu = {
    async popup(at, window) {
      calls.push({ at, window });
    },
  };
  const at = { x: 1, y: 2 };
  const window = { label: "main" };

  await showPetContextMenu(menu, at, window);

  assert.deepEqual(calls, [{ at, window }]);
});
