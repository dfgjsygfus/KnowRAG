import { backendUrl } from "./backendUrl.js";

export async function streamQuestion(question, topK, onEvent, fetchImpl = fetch, signal = null) {
  const response = await fetchImpl(backendUrl("/api/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
    signal,
  });

  if (!response.ok) {
    let message = `问答请求失败 (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the status-based message when the backend did not return JSON.
    }
    throw new Error(message);
  }
  if (!response.body) {
    throw new Error("浏览器不支持流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminalEventReceived = false;
  const handleBlock = (block) => {
    if (terminalEventReceived) return;
    emitBlock(block, (event, data) => {
      if (event === "done" || event === "error") terminalEventReceived = true;
      onEvent(event, data);
    });
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replaceAll("\r\n", "\n");

    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      handleBlock(block);
    }

    if (done) {
      if (buffer.trim()) handleBlock(buffer);
      break;
    }
  }

  if (!terminalEventReceived) {
    throw new Error("The answer stream ended before completion.");
  }
}

function emitBlock(block, onEvent) {
  let event = "message";
  const dataLines = [];

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return;

  const rawData = dataLines.join("\n");
  try {
    onEvent(event, JSON.parse(rawData));
  } catch {
    onEvent("error", { message: "后端返回了无法解析的流式消息。" });
  }
}
