const ADMIN_WINDOW_LABEL = "admin";

export function adminWindowUrl() {
  return "/?view=admin";
}

export async function openAdminWindow(WebviewWindowClass) {
  const existingWindow = await WebviewWindowClass.getByLabel(ADMIN_WINDOW_LABEL);
  if (existingWindow) {
    await existingWindow.unminimize();
    await existingWindow.show();
    await existingWindow.setFocus();
    return existingWindow;
  }

  return new WebviewWindowClass(ADMIN_WINDOW_LABEL, {
    url: adminWindowUrl(),
    title: "KnowRAG 管理台",
    width: 1180,
    height: 780,
    minWidth: 900,
    minHeight: 620,
    resizable: true,
    decorations: true,
    center: true,
    focus: true,
  });
}
