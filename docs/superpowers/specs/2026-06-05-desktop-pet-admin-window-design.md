# Desktop Pet Admin Window Design

Date: 2026-06-05

## Goal

Keep left-click on the desktop pet for question answering, and use right-click to open the existing KnowRAG management console in a separate in-app window.

## Design

- FastAPI serves the existing `frontend/index.html` at `GET /admin`.
- Right-clicking the pet suppresses the browser context menu and opens a Tauri webview window labeled `admin`.
- If the admin window already exists, right-clicking restores, shows, and focuses it instead of creating a duplicate.
- The admin window loads `http://127.0.0.1:8000/admin`, uses normal window decorations, and is resizable.
- The remote admin window receives no Tauri IPC capabilities; only the local main pet window may create and focus it.

## Verification

- Route tests verify `/admin` returns the existing management console.
- JavaScript tests verify first-open creation and repeated-open window reuse.
- Full Python tests, desktop-pet JavaScript tests, Vite build, Tauri check, and release build must pass.
