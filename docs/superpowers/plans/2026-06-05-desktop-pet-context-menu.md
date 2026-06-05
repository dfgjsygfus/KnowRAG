# Desktop Pet Context Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace direct right-click behavior with a reusable native context menu.

**Architecture:** A focused `petContextMenu.js` module creates the native Tauri menu and maps menu actions to callbacks owned by `App.vue`. The app lazily creates the menu on first right-click and reuses it afterward.

**Tech Stack:** Vue 3, Tauri 2 menu API, Node test runner

---

### Task 1: Native Context Menu Module

**Files:**
- Create: `desktop-pet/src/lib/petContextMenu.js`
- Create: `desktop-pet/src/lib/petContextMenu.test.js`

- [ ] Add failing tests for item order, action dispatch, and popup.
- [ ] Run `npm.cmd test` and confirm failure because the module is missing.
- [ ] Implement native menu creation and popup helpers.
- [ ] Re-run `npm.cmd test`.

### Task 2: Pet Integration and Release

**Files:**
- Modify: `desktop-pet/src/App.vue`

- [ ] Replace direct right-click management opening with native menu popup.
- [ ] Run JavaScript tests, Vite build, Tauri check, and release build.
- [ ] Replace and restart the desktop-pet executable.
