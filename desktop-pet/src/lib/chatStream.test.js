import assert from "node:assert/strict";
import test from "node:test";

import { streamQuestion } from "./chatStream.js";

test("streamQuestion rejects a stream that ends without a terminal event", async () => {
  const events = [];
  const fetchImpl = async () => responseFromChunks([
    'event: status\ndata: {"state":"answering"}\n\n',
    'event: delta\ndata: {"content":"partial"}\n\n',
  ]);

  await assert.rejects(
    streamQuestion("question", 5, (event, data) => events.push([event, data]), fetchImpl),
    /ended before completion/i,
  );
  assert.deepEqual(events.at(-1), ["delta", { content: "partial" }]);
});

test("streamQuestion accepts a completed stream", async () => {
  const events = [];
  const fetchImpl = async () => responseFromChunks([
    'event: delta\ndata: {"content":"answer"}\n\n',
    'event: done\ndata: {"state":"success"}\n\n',
  ]);

  await streamQuestion("question", 5, (event, data) => events.push([event, data]), fetchImpl);

  assert.deepEqual(events.at(-1), ["done", { state: "success" }]);
});

test("streamQuestion forwards routing events", async () => {
  const events = [];
  const fetchImpl = async () => responseFromChunks([
    'event: routing\ndata: {"intent":"casual_chat","confidence":1,"method":"rule"}\n\n',
    'event: done\ndata: {"state":"success"}\n\n',
  ]);

  await streamQuestion("你好", 5, (event, data) => events.push([event, data]), fetchImpl);

  assert.deepEqual(events[0], [
    "routing",
    { intent: "casual_chat", confidence: 1, method: "rule" },
  ]);
});

test("streamQuestion ignores events after the first terminal event", async () => {
  const events = [];
  const fetchImpl = async () => responseFromChunks([
    'event: error\ndata: {"message":"failed"}\n\n',
    'event: done\ndata: {"state":"success"}\n\n',
  ]);

  await streamQuestion("question", 5, (event, data) => events.push([event, data]), fetchImpl);

  assert.deepEqual(events, [["error", { message: "failed" }]]);
});

test("streamQuestion passes the abort signal to fetch", async () => {
  const calls = [];
  const controller = new AbortController();
  const fetchImpl = async (url, options) => {
    calls.push(options);
    return responseFromChunks([
      'event: done\ndata: {"state":"success"}\n\n',
    ]);
  };

  await streamQuestion("q", 5, () => {}, fetchImpl, controller.signal);

  assert.equal(calls[0].signal, controller.signal);
});

test("streamQuestion forwards an AbortError from fetch", async () => {
  const controller = new AbortController();
  const fetchImpl = async () => {
    const err = new Error("The user aborted a request.");
    err.name = "AbortError";
    throw err;
  };

  await assert.rejects(
    streamQuestion("q", 5, () => {}, fetchImpl, controller.signal),
    /abort/i,
  );
});

function responseFromChunks(chunks) {
  const encoder = new TextEncoder();
  return {
    ok: true,
    body: new ReadableStream({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    }),
  };
}
