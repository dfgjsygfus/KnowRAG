export function createPetContextMenu(MenuClass, actions) {
  return MenuClass.new({
    items: [
      {
        id: "open-admin",
        text: "打开管理台",
        action: actions.openAdmin,
      },
      {
        id: "toggle-panel",
        text: "展开/收起问答",
        action: actions.togglePanel,
      },
      {
        item: "Separator",
      },
      {
        id: "exit-pet",
        text: "退出桌宠",
        action: actions.exitPet,
      },
    ],
  });
}

export function showPetContextMenu(menu) {
  return menu.popup();
}
