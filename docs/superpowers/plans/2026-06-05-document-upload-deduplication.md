# Document Upload Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent identical document content from creating duplicate SQLite records and duplicate indexable document objects.

**Architecture:** The repository computes SHA-256 and performs a transactional find-or-create by `content_hash`. The service exposes whether the upload was deduplicated, and the admin frontend reloads the authoritative backend list after upload.

**Tech Stack:** Python, SQLite, FastAPI, unittest, vanilla JavaScript

---

### Task 1: Add failing duplicate-upload tests

**Files:**
- Modify: `tests/test_document_repository.py`
- Modify: `tests/test_documents_routes.py`
- Modify: `tests/test_admin_frontend.py`

- [ ] Add a repository test asserting identical content returns one stored document.
- [ ] Add an API test asserting the second upload returns the original ID and `deduplicated: true`.
- [ ] Add a frontend source test asserting upload success reloads the backend list.
- [ ] Run the focused tests and confirm they fail for the missing behavior.

### Task 2: Implement repository and service deduplication

**Files:**
- Modify: `backend/app/services/document_repository.py`
- Modify: `backend/app/services/document_service.py`

- [ ] Add `create_or_get_document()` using a SQLite immediate transaction and `content_hash` lookup.
- [ ] Keep `create_document()` compatible by delegating to the new method.
- [ ] Add a non-unique `content_hash` index for efficient lookup.
- [ ] Add `deduplicated` to upload responses.
- [ ] Run repository and route tests and confirm they pass.

### Task 3: Prevent duplicate rows in the admin frontend

**Files:**
- Modify: `frontend/app.js`

- [ ] Replace direct `files.unshift()` after upload with `await loadDocuments()`.
- [ ] Show a clear toast when the backend reports a duplicate.
- [ ] Run the frontend test and confirm it passes.

### Task 4: Verify regression safety

**Files:**
- Verify: `tests/`

- [ ] Run the complete Python unittest suite.
- [ ] Review `git diff` to ensure only duplicate-upload behavior and documentation changed.
