import { LogicalPosition, LogicalSize } from "@tauri-apps/api/dpi";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";

import { getPetAnchorOffset, getPetSize } from "./petScale.js";

export const PET_CHAT_WINDOW_LABEL = "pet-chat-input";
export const PET_CHAT_WINDOW_WIDTH = 300;
export const PET_CHAT_WINDOW_HEIGHT = 80;
const PET_CHAT_GAP = 8;

export function createPetChatWindowUrl() {
  return "/?view=pet-chat";
}

export function getPetChatWindowPosition(mainPosition, petAnchor, shellSize) {
  return {
    x: Math.round(mainPosition.x + petAnchor.x - PET_CHAT_WINDOW_WIDTH / 2),
    y: Math.round(mainPosition.y + petAnchor.y + shellSize / 2 + PET_CHAT_GAP),
  };
}

export function getPetChatWindowPositionFromPetRect(mainPosition, petBounds) {
  return {
    x: Math.round(mainPosition.x + petBounds.left + petBounds.width / 2 - PET_CHAT_WINDOW_WIDTH / 2),
    y: Math.round(mainPosition.y + petBounds.bottom + PET_CHAT_GAP),
  };
}

async function waitForWebviewWindowCreated(window) {
  await new Promise((resolve, reject) => {
    let settled = false;
    const finish = (handler, value) => {
      if (settled) return;
      settled = true;
      handler(value);
    };

    window.once("tauri://created", () => finish(resolve)).catch(reject);
    window.once("tauri://error", (event) => {
      const message = event?.payload || "Failed to create pet chat input window.";
      finish(reject, new Error(String(message)));
    }).catch(reject);
  });
}

async function getPetChatWindowPlacement({
  currentWindow,
  petScale,
  petBounds,
}) {
  const scaleFactor = await currentWindow.scaleFactor();
  const mainPosition = (await currentWindow.outerPosition()).toLogical(scaleFactor);
  const mainSize = (await currentWindow.outerSize()).toLogical(scaleFactor);
  return petBounds
    ? getPetChatWindowPositionFromPetRect(mainPosition, petBounds)
    : getPetChatWindowPosition(
      mainPosition,
      getPetAnchorOffset("pet", petScale, mainSize),
      getPetSize(petScale) + 36,
    );
}

export async function positionPetChatWindow({
  WebviewWindowClass = WebviewWindow,
  currentWindow,
  petScale,
  petBounds,
  bringToFront = false,
} = {}) {
  const existing = await WebviewWindowClass.getByLabel(PET_CHAT_WINDOW_LABEL);
  if (!existing) return null;

  const position = await getPetChatWindowPlacement({ currentWindow, petScale, petBounds });
  await existing.setSize(new LogicalSize(PET_CHAT_WINDOW_WIDTH, PET_CHAT_WINDOW_HEIGHT));
  await existing.setPosition(new LogicalPosition(position.x, position.y));
  if (bringToFront) {
    await existing.show();
    await existing.setFocus();
  }
  return existing;
}

export async function openPetChatWindow({
  WebviewWindowClass = WebviewWindow,
  currentWindow,
  petScale,
  petBounds,
} = {}) {
  const position = await getPetChatWindowPlacement({ currentWindow, petScale, petBounds });

  const existing = await WebviewWindowClass.getByLabel(PET_CHAT_WINDOW_LABEL);
  if (existing) {
    await positionPetChatWindow({
      WebviewWindowClass,
      currentWindow,
      petScale,
      petBounds,
      bringToFront: true,
    });
    return existing;
  }

  const win = new WebviewWindowClass(PET_CHAT_WINDOW_LABEL, {
    url: createPetChatWindowUrl(),
    title: "KnowRAG Chat Input",
    width: PET_CHAT_WINDOW_WIDTH,
    height: PET_CHAT_WINDOW_HEIGHT,
    decorations: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    shadow: false,
    visible: false,
  });

  await waitForWebviewWindowCreated(win);
  await win.setSize(new LogicalSize(PET_CHAT_WINDOW_WIDTH, PET_CHAT_WINDOW_HEIGHT));
  await win.setPosition(new LogicalPosition(position.x, position.y));
  await win.show();
  await win.setFocus();
  return win;
}

export async function closePetChatWindow(WebviewWindowClass = WebviewWindow) {
  const win = await WebviewWindowClass.getByLabel(PET_CHAT_WINDOW_LABEL);
  if (win) await win.close();
}
