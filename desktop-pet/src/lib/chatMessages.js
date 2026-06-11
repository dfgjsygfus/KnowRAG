export function createUserMessage(id, content) {
  return {
    id,
    role: "user",
    content,
  };
}

export function createAssistantMessage(id) {
  return {
    id,
    role: "assistant",
    content: "",
    status: "thinking",
    routeIntent: "",
    sources: [],
    errorMessage: "",
  };
}

export function appendAssistantDelta(messages, messageId, content) {
  return updateAssistantMessage(messages, messageId, (message) => ({
    content: `${message.content}${content || ""}`,
  }));
}

export function updateAssistantMessage(messages, messageId, patchOrUpdater) {
  return messages.map((message) => {
    if (message.id !== messageId || message.role !== "assistant") return message;
    const patch = typeof patchOrUpdater === "function" ? patchOrUpdater(message) : patchOrUpdater;
    return { ...message, ...patch };
  });
}
