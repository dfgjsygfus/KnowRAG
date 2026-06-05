# Retrieval Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repeatable retrieval evaluation dataset, Recall@K/MRR reporting, score-threshold recommendation, and safe structured retrieval logging.

**Architecture:** A focused evaluation service loads JSONL cases and evaluates an injected retriever. A small CLI uses the production retriever and writes reports. The existing retrieval service emits metadata-only structured logs after successful searches.

**Tech Stack:** Python, unittest, JSONL, existing FastAPI/Milvus retrieval services

---

### Task 1: Add evaluation models, loader, and metric tests

**Files:**
- Create: `backend/app/services/retrieval_evaluation.py`
- Create: `tests/test_retrieval_evaluation.py`

- [ ] Write failing tests for JSONL validation, Recall@K, MRR, failed retrieval handling, and threshold recommendation.
- [ ] Run the focused tests and verify they fail because the service is missing.
- [ ] Implement the minimum loader and evaluation functions.
- [ ] Run focused tests and verify they pass.

### Task 2: Add retrieval structured logging

**Files:**
- Modify: `backend/app/services/retrieval_service.py`
- Modify: `tests/test_retrieval_service.py`
- Modify: `.env.example`

- [ ] Write a failing test that captures the retrieval log and asserts it contains timing and hit metadata without content or vectors.
- [ ] Implement metadata-only structured logging controlled by `RETRIEVAL_LOG_ENABLED`.
- [ ] Run retrieval service tests and verify they pass.

### Task 3: Add seed dataset and CLI

**Files:**
- Create: `evaluation/retrieval_seed.jsonl`
- Create: `scripts/evaluate_retrieval.py`
- Modify: `.gitignore`
- Modify: `README.md`

- [ ] Add 15 validated seed cases based on the current ChiefArchitect fixture.
- [ ] Add CLI argument parsing, evaluation execution, terminal summary, and JSON report output.
- [ ] Validate the dataset through the evaluation loader.
- [ ] Run CLI help without requiring Milvus.

### Task 4: Verify regression safety

**Files:**
- Verify: `tests/`
- Verify: `desktop-pet/`

- [ ] Run complete Python unittest suite.
- [ ] Run desktop pet Node tests.
- [ ] Run `python -m compileall -q backend scripts tests`.
- [ ] Run `git diff --check`.
