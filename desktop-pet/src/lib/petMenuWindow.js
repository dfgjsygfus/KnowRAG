import { LogicalSize, PhysicalPosition } from "@tauri-apps/api/dpi";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";

const MENU_WINDOW_LABEL = "pet-context-menu";
const MENU_WINDOW_WIDTH = 360;
const MENU_WINDOW_HEIGHT = 360;

/**
 * Open the standalone context-menu window at the given screen position.
 * The menu is transient, so recreate it each time instead of reusing a
 * closing window whose native position/focus state may be stale.
 *
 * @param {{ x: number, y: number, chatSurface: string, petScale: number }} opts
 */
export async function openPetMenuWindow({ x, y, chatSurface, petScale }) {
  const params = new URLSearchParams({
    view: "pet-menu",
    chatSurface,
    petScale: String(petScale),
  });
  const url = `/?${params.toString()}`;

  const existing = await WebviewWindow.getByLabel(MENU_WINDOW_LABEL);
  if (existing) {
    await existing.close();
    await waitForMenuWindowClosed();
  }

  const win = new WebviewWindow(MENU_WINDOW_LABEL, {
    url,
    title: "KnowRAG Menu",
    width: MENU_WINDOW_WIDTH,
    height: MENU_WINDOW_HEIGHT,
    decorations: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    shadow: false,
    visible: false,
  });

  await win.setSize(new LogicalSize(MENU_WINDOW_WIDTH, MENU_WINDOW_HEIGHT));
  await win.setPosition(new PhysicalPosition(x, y));
  await win.show();
  await win.setFocus();
}

async function waitForMenuWindowClosed() {
  for (let i = 0; i < 10; i += 1) {
    const win = await WebviewWindow.getByLabel(MENU_WINDOW_LABEL);
    if (!win) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
}

/**
 * Programmatically close the menu window (e.g. on main-window blur).
 */
export async function closePetMenuWindow() {
  try {
    const win = await WebviewWindow.getByLabel(MENU_WINDOW_LABEL);
    if (win) await win.close();
  } catch {
    // Window already gone — fine.
  }
}
