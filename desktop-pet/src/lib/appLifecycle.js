export async function exitDesktopPet(getAllWindows, currentWindow) {
  const windows = await getAllWindows();
  for (const window of windows) {
    if (window.label !== currentWindow.label) await window.close();
  }
  await currentWindow.close();
}
