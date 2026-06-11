import assert from "node:assert/strict";
import test from "node:test";

import {
  appendAssistantDelta,
  createAssistantMessage,
  createUserMessage,
  updateAssistantMessage,
} from "./chatMessages.js";

test("chat messages create user and assistant bubbles", () => {
  assert.deepEqual(createUserMessage("u1", "hello"), {
    id: "u1",
    role: "user",
    content: "hello",
  });

  assert.deepEqual(createAssistantMessage("a1"), {
    id: "a1",
    role: "assistant",
    content: "",
    status: "thinking",
    routeIntent: "",
    sources: [],
    errorMessage: "",
  });
});

test("appendAssistantDelta streams text into only the matching assistant message", () => {
  const messages = [
    createAssistantMessage("a1"),
    createAssistantMessage("a2"),
  ];

  const updated = appendAssistantDelta(messages, "a2", "answer");

  assert.equal(updated[0].content, "");
  assert.equal(updated[1].content, "answer");
  assert.notEqual(updated, messages);
});

test("updateAssistantMessage stores routing sources and errors on the assistant bubble", () => {
  const messages = [createAssistantMessage("a1")];

  const updated = updateAssistantMessage(messages, "a1", {
    status: "error",
    routeIntent: "knowledge_query",
    sources: [{ chunk_id: "c1", citation: 1 }],
    errorMessage: "failed",
  });

  assert.equal(updated[0].status, "error");
  assert.equal(updated[0].routeIntent, "knowledge_query");
  assert.deepEqual(updated[0].sources, [{ chunk_id: "c1", citation: 1 }]);
  assert.equal(updated[0].errorMessage, "failed");
});
