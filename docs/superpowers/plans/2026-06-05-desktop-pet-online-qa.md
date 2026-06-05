# Desktop Pet Online QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static-image Tauri desktop pet that answers one question at a time through a streaming RAG API with cited sources.

**Architecture:** FastAPI owns retrieval, prompt construction, generation, and SSE event formatting. A small OpenAI-compatible client streams model deltas. The independent `desktop-pet/` Tauri + Vue client renders the static pet, expands a chat panel, consumes SSE, and displays answer sources.

**Tech Stack:** Python 3, FastAPI, unittest, OpenAI-compatible HTTP API, Vue 3, Vite, Tauri 2, Rust

---

### Task 1: OpenAI-Compatible Streaming Client

**Files:**
- Create: `backend/app/services/openai_chat.py`
- Create: `tests/test_openai_chat.py`

- [x] Write failing tests proving the client validates configuration, sends the expected chat-completions payload, and yields SSE delta text.
- [x] Run `python -m unittest tests.test_openai_chat -v` and confirm the tests fail because the module is missing.
- [x] Implement `OpenAIChatClient.stream_chat()` with an injectable transport and standard-library HTTP transport.
- [x] Run `python -m unittest tests.test_openai_chat -v` and confirm all client tests pass.

### Task 2: RAG Streaming Service and API

**Files:**
- Create: `backend/app/schemas/chat.py`
- Create: `backend/app/services/rag_service.py`
- Create: `backend/app/api/chat.py`
- Modify: `main.py`
- Create: `tests/test_rag_service.py`
- Create: `tests/test_chat_routes.py`

- [x] Write failing service tests for prompt context numbering, streamed deltas, sources, and empty-retrieval short circuit.
- [x] Run `python -m unittest tests.test_rag_service -v` and confirm missing RAG service failures.
- [x] Implement the minimal RAG stream event generator and source serialization.
- [x] Run `python -m unittest tests.test_rag_service -v` and confirm service tests pass.
- [x] Write a failing route test for `POST /api/chat/stream` SSE output.
- [x] Implement the chat router and register it in `main.py`.
- [x] Run `python -m unittest tests.test_chat_routes -v` and confirm route tests pass.

### Task 3: Static Desktop Pet Client

**Files:**
- Create: `desktop-pet/package.json`
- Create: `desktop-pet/index.html`
- Create: `desktop-pet/src/main.js`
- Create: `desktop-pet/src/App.vue`
- Create: `desktop-pet/src/style.css`
- Create: `desktop-pet/src/lib/chatStream.js`
- Create: `desktop-pet/src/assets/pet.png`
- Create: `desktop-pet/src-tauri/Cargo.toml`
- Create: `desktop-pet/src-tauri/build.rs`
- Create: `desktop-pet/src-tauri/src/main.rs`
- Create: `desktop-pet/src-tauri/tauri.conf.json`
- Create: `desktop-pet/vite.config.js`

- [x] Scaffold the minimal Vue + Vite + Tauri 2 project.
- [x] Copy the supplied image unchanged to `desktop-pet/src/assets/pet.png`.
- [x] Implement a transparent always-on-top window with a draggable static pet.
- [x] Implement click-to-expand single-turn question panel.
- [x] Implement robust SSE parsing and render status, streamed answer, and expandable sources.
- [x] Run `npm.cmd install` in `desktop-pet`.
- [x] Run `npm.cmd run build` and fix all frontend build errors.
- [x] Run `cargo check --manifest-path desktop-pet/src-tauri/Cargo.toml` and fix all Rust/Tauri errors.

### Task 4: Verification

**Files:**
- Modify only files required by verification findings.

- [x] Run `python -m unittest discover -s tests -v` and resolve regressions.
- [x] Run `npm.cmd run build` in `desktop-pet`.
- [x] Run `cargo check --manifest-path desktop-pet/src-tauri/Cargo.toml`.
- [x] Review the final diff against the design scope and remove unrelated changes.
