# Desktop Pet Admin Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open the existing KnowRAG management console in a reusable in-app window when the user right-clicks the desktop pet.

**Architecture:** FastAPI exposes the existing management HTML at `/admin`. A small desktop-pet window helper creates or focuses a Tauri `WebviewWindow`, while `App.vue` binds that helper to the pet image context-menu event.

**Tech Stack:** FastAPI, unittest, Vue 3, Tauri 2, Node test runner

---

### Task 1: Management Console Route

**Files:**
- Modify: `main.py`
- Modify: `tests/test_chat_routes.py`

- [ ] Add a failing route test asserting `GET /admin` returns the KnowRAG management console HTML.
- [ ] Run `python -m unittest tests.test_chat_routes -v` and confirm the route test fails with 404.
- [ ] Add a FastAPI `FileResponse` route that returns `frontend/index.html`.
- [ ] Re-run the route test and confirm it passes.

### Task 2: Reusable Admin Window

**Files:**
- Create: `desktop-pet/src/lib/adminWindow.js`
- Create: `desktop-pet/src/lib/adminWindow.test.js`
- Modify: `desktop-pet/src/App.vue`
- Modify: `desktop-pet/src-tauri/capabilities/default.json`

- [ ] Add failing Node tests for creating the admin window once and focusing an existing window.
- [ ] Run `npm.cmd test` and confirm the new tests fail.
- [ ] Implement `openAdminWindow`, bind it to the pet button's context-menu event, and grant only the required window creation/focus permissions.
- [ ] Re-run `npm.cmd test` and confirm all tests pass.

### Task 3: Verification and Release

**Files:**
- Modify only files required by verification findings.

- [ ] Run `python -m unittest discover -s tests -q`.
- [ ] Run `npm.cmd test` and `npm.cmd run build` in `desktop-pet`.
- [ ] Run Tauri check and release build with the MSVC target.
- [ ] Replace the running desktop-pet executable and restart the backend and pet.
- [ ] Verify `/admin`, the desktop-pet process, and release executable hash.
