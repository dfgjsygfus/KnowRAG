import assert from "node:assert/strict";
import test from "node:test";

import { createPetContextMenu, showPetContextMenu } from "./petContextMenu.js";

test("createPetContextMenu builds the approved native menu and dispatches actions", async () => {
  const actions = [];
  const fakeMenu = { popup: async () => {} };
  class FakeMenu {
    static async new(options) {
      FakeMenu.options = options;
      return fakeMenu;
    }
  }

  const menu = await createPetContextMenu(FakeMenu, {
    openAdmin: () => actions.push("admin"),
    togglePanel: () => actions.push("toggle"),
    exitPet: () => actions.push("exit"),
  });

  assert.equal(menu, fakeMenu);
  assert.deepEqual(
    FakeMenu.options.items.map((item) => item.text || item.item),
    ["打开管理台", "展开/收起问答", "Separator", "退出桌宠"],
  );
  FakeMenu.options.items[0].action();
  FakeMenu.options.items[1].action();
  FakeMenu.options.items[3].action();
  assert.deepEqual(actions, ["admin", "toggle", "exit"]);
});

test("showPetContextMenu pops up an existing native menu", async () => {
  let popupCount = 0;
  const menu = {
    async popup() {
      popupCount += 1;
    },
  };

  await showPetContextMenu(menu);

  assert.equal(popupCount, 1);
});
