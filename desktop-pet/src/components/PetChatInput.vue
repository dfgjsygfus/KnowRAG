<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { emitTo } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";

const question = ref("");
const inputRef = ref(null);

async function closeWindow() {
  try {
    await emitTo("main", "pet-chat-closed");
  } catch {
    // Browser dev mode has no main Tauri window to receive the event.
  }
  try {
    await getCurrentWindow().close();
  } catch {
    window.close();
  }
}

async function submitQuestion() {
  const normalized = question.value.trim();
  if (!normalized) return;

  try {
    await emitTo("main", "pet-chat-submit", { question: normalized });
  } catch {
    // Browser dev mode has no main Tauri window to receive the event.
  }
  question.value = "";
  await closeWindow();
}

function onKeyDown(event) {
  if (event.key === "Escape") {
    event.preventDefault();
    void closeWindow();
  }
}

onMounted(async () => {
  document.addEventListener("keydown", onKeyDown);
  await nextTick();
  inputRef.value?.focus();
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeyDown);
});
</script>

<template>
  <main class="chat-input-window">
    <form class="chat-input-form" @submit.prevent="submitQuestion">
      <input
        ref="inputRef"
        v-model="question"
        class="chat-input-field"
        maxlength="200"
        placeholder="问一句..."
        @keydown.enter.exact.prevent="submitQuestion"
      />
      <button class="chat-input-send" type="submit" :disabled="!question.trim()">➤</button>
    </form>
  </main>
</template>

<style scoped>
.chat-input-window {
  width: 100vw;
  height: 100vh;
  display: grid;
  place-items: center;
  padding: 8px;
  background: transparent;
  overflow: hidden;
}

.chat-input-form {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px;
  border: 0.5px solid rgba(0, 0, 0, 0.06);
  border-radius: 24px;
  background: rgba(255, 247, 241, 0.96);
  box-shadow: 0 6px 24px rgba(140, 100, 60, 0.18);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.chat-input-field {
  min-width: 0;
  flex: 1;
  height: 34px;
  border: 0;
  border-radius: 20px;
  padding: 0 14px;
  background: transparent;
  color: #3a2a1c;
  font: inherit;
  font-size: 13px;
  outline: none;
}

.chat-input-field::placeholder {
  color: #ad9276;
}

.chat-input-send {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: #e8967a;
  color: #ffffff;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.15s, transform 0.15s;
}

.chat-input-send:hover:not(:disabled) {
  background: #d8806e;
  transform: translateY(-1px);
}

.chat-input-send:disabled {
  cursor: default;
  opacity: 0.45;
}
</style>
