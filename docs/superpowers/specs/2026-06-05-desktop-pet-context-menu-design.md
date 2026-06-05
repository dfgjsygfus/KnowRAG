# Desktop Pet Context Menu Design

Date: 2026-06-05

## Goal

Right-clicking the desktop pet opens a native system context menu instead of immediately opening the management console.

## Menu

1. Open management console
2. Expand or collapse question panel
3. Separator
4. Exit desktop pet

The menu is created once and reused. Existing management-window reuse behavior remains unchanged.

## Verification

- Unit tests verify menu labels, order, separator, action dispatch, and popup reuse.
- Desktop-pet JavaScript tests, Vite build, Tauri check, and release build must pass.
