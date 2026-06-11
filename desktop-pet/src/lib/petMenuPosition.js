/**
 * Compute the screen position for the context menu window so it stays
 * inside the monitor bounds, flipping left/up when it would overflow.
 *
 * All values are in logical (CSS) pixels and use global screen coordinates.
 *
 * @param {{ clickX: number, clickY: number, menuWidth: number, menuHeight: number, monitorLeft: number, monitorTop: number, monitorRight: number, monitorBottom: number }} params
 * @returns {{ x: number, y: number }}
 */
export function getMenuPositionNearClick({
  clickX,
  clickY,
  menuWidth,
  menuHeight,
  monitorLeft,
  monitorTop,
  monitorRight,
  monitorBottom,
}) {
  const MARGIN = 8;

  let x = clickX;
  let y = clickY;

  // Flip left if menu overflows the right edge of this monitor
  if (x + menuWidth > monitorRight - MARGIN) {
    x = clickX - menuWidth;
  }

  // Flip up if menu overflows the bottom edge of this monitor
  if (y + menuHeight > monitorBottom - MARGIN) {
    y = clickY - menuHeight;
  }

  // Clamp to stay at least MARGIN pixels inside this monitor on all four sides
  const minX = monitorLeft + MARGIN;
  const minY = monitorTop + MARGIN;
  const maxX = Math.max(minX, monitorRight - MARGIN - menuWidth);
  const maxY = Math.max(minY, monitorBottom - MARGIN - menuHeight);

  return {
    x: Math.min(maxX, Math.max(minX, x)),
    y: Math.min(maxY, Math.max(minY, y)),
  };
}
