const SCALE_ITEMS = [
  { scale: 0.8, text: "小" },
  { scale: 1, text: "中" },
  { scale: 1.2, text: "大" },
  { scale: 1.4, text: "特大" },
];

/**
 * Build the desktop pet context menu using Tauri's native popup menu.
 *
 * @param {{ new: (options: object) => Promise<object> }} MenuClass
 * @param {{ openAdmin: Function, toggleChat: Function, openFull: Function, setScale: Function, exitPet: Function }} actions
 * @param {{ chatSurface: string, petScale: number }} state
 */
export function createPetContextMenu(MenuClass, actions, state) {
  const toggleText =
    state.chatSurface === "pet" ? "打开输入框" : "关闭输入框";

  return MenuClass.new({
    items: [
      {
        id: "open-admin",
        text: "打开管理台",
        action: () => void actions.openAdmin(),
      },
      {
        id: "toggle-chat",
        text: toggleText,
        action: () => void actions.toggleChat(),
      },
      {
        id: "open-full-chat",
        text: "打开完整聊天",
        action: () => void actions.openFull(),
      },
      {
        item: "Separator",
      },
      {
        id: "pet-scale",
        text: "调整大小",
        items: SCALE_ITEMS.map(({ scale, text }) => ({
          id: `pet-scale-${scale}`,
          text: Math.abs(state.petScale - scale) < 0.001 ? `${text} ✓` : text,
          action: () => void actions.setScale(scale),
        })),
      },
      {
        item: "Separator",
      },
      {
        id: "exit-pet",
        text: "退出",
        action: () => void actions.exitPet(),
      },
    ],
  });
}

export function showPetContextMenu(menu, at, window) {
  return menu.popup(at, window);
}
