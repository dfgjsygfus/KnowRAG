# Query Intent Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route user questions between knowledge-base RAG and direct casual chat before retrieval.

**Architecture:** A dedicated query router performs deterministic rule classification first and uses an injected OpenAI-compatible classifier only for ambiguous questions. The existing RAG stream orchestrator emits a routing event and selects either retrieval-backed answering or direct chat.

**Tech Stack:** Python, FastAPI SSE, unittest, existing OpenAI-compatible chat client

---

### Task 1: Add query routing schemas and rule classifier

**Files:**
- Create: `backend/app/schemas/query_routing.py`
- Create: `backend/app/services/query_router.py`
- Create: `tests/test_query_router.py`

- [ ] Write failing tests for casual-chat rules, knowledge-query rules, model fallback, low-confidence fallback, and model errors.
- [ ] Implement routing schemas and rule-first routing service.
- [ ] Run focused query router tests.

### Task 2: Add routing to chat orchestration

**Files:**
- Modify: `backend/app/services/rag_service.py`
- Modify: `tests/test_rag_service.py`
- Modify: `tests/test_chat_routes.py`

- [ ] Write failing tests asserting routing events and no retrieval for casual chat.
- [ ] Add casual-chat prompt and route-aware stream orchestration.
- [ ] Verify existing knowledge-query behavior remains unchanged.

### Task 3: Add configuration and frontend routing event support

**Files:**
- Modify: `.env.example`
- Modify: `desktop-pet/src/lib/chatStream.js`
- Modify: `desktop-pet/src/lib/chatStream.test.js`
- Modify: `desktop-pet/src/App.vue`

- [ ] Add query router configuration defaults.
- [ ] Parse routing SSE events.
- [ ] Display the selected route in the desktop pet chat status.
- [ ] Run desktop pet tests.

### Task 4: Verify regression safety

**Files:**
- Verify: `tests/`
- Verify: `desktop-pet/`

- [ ] Run complete Python unittest suite.
- [ ] Run desktop pet Node tests.
- [ ] Run compileall and diff checks.
