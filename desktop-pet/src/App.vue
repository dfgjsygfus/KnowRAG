<script setup>
import { nextTick, onBeforeUnmount, ref } from "vue";
import { LogicalSize } from "@tauri-apps/api/dpi";
import { Menu } from "@tauri-apps/api/menu";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";
import { getAllWindows, getCurrentWindow } from "@tauri-apps/api/window";

import petImage from "./assets/pet.webp";
import { openAdminWindow } from "./lib/adminWindow";
import { exitDesktopPet } from "./lib/appLifecycle";
import { streamQuestion } from "./lib/chatStream";
import { createPetContextMenu, showPetContextMenu } from "./lib/petContextMenu";

const expanded = ref(false);
const question = ref("");
const answer = ref("");
const sources = ref([]);
const state = ref("idle");
const routeIntent = ref("");
const errorMessage = ref("");
const answerArea = ref(null);
const topK = 5;
let petContextMenuPromise;
let abortController = null;

onBeforeUnmount(() => {
  if (abortController) abortController.abort();
});

const stateText = {
  idle: "输入问题，我会判断是否需要检索知识库。",
  thinking: "正在判断问题意图...",
  answering: "正在组织答案。",
  empty: "资料里暂时没有找到答案。",
  error: "问答出错，可以再试一次。",
};

const routeText = {
  knowledge_query: "知识库问答",
  casual_chat: "普通闲聊",
};

async function togglePanel() {
  expanded.value = !expanded.value;
  await resizeWindow(expanded.value);
}

async function resizeWindow(isExpanded) {
  try {
    const window = getCurrentWindow();
    await window.setSize(isExpanded ? new LogicalSize(760, 620) : new LogicalSize(280, 340));
  } catch {
    // Running in a regular browser during UI development.
  }
}

async function exitPet() {
  try {
    await exitDesktopPet(getAllWindows, getCurrentWindow());
  } catch {
    window.close();
  }
}

async function openManagement() {
  try {
    await openAdminWindow(WebviewWindow);
  } catch (error) {
    state.value = "error";
    errorMessage.value = error.message || "无法打开 KnowRAG 管理台。";
  }
}

async function showContextMenu() {
  try {
    petContextMenuPromise ||= createPetContextMenu(Menu, {
      openAdmin: () => void openManagement(),
      togglePanel: () => void togglePanel(),
      exitPet: () => void exitPet(),
    });
    await showPetContextMenu(await petContextMenuPromise);
  } catch (error) {
    petContextMenuPromise = null;
    state.value = "error";
    errorMessage.value = error.message || "无法打开桌宠菜单。";
  }
}

async function onPetMouseDown() {
  try {
    await getCurrentWindow().startDragging();
  } catch {
    // Not in Tauri environment
  }
}

async function askQuestion() {
  const normalized = question.value.trim();
  if (!normalized || state.value === "thinking" || state.value === "answering") return;

  if (abortController) abortController.abort();
  abortController = new AbortController();

  answer.value = "";
  sources.value = [];
  routeIntent.value = "";
  errorMessage.value = "";
  state.value = "thinking";

  question.value = "";

  try {
    await streamQuestion(normalized, topK, handleStreamEvent, fetch, abortController.signal);
  } catch (error) {
    if (error.name === "AbortError") return;
    state.value = "error";
    errorMessage.value = error.message || "无法连接 KnowRAG 后端。";
  } finally {
    if (abortController && !abortController.signal.aborted) {
      abortController = null;
    }
  }
}

function handleStreamEvent(event, data) {
  if (event === "status") state.value = data.state || state.value;
  if (event === "routing") routeIntent.value = data.intent || "";
  if (event === "sources") sources.value = data.sources || [];
  if (event === "delta") {
    answer.value += data.content || "";
    scrollAnswerToBottom();
  }
  if (event === "done") state.value = data.state || "success";
  if (event === "error") {
    state.value = "error";
    errorMessage.value = data.message || "问答服务发生错误。";
  }
}

async function scrollAnswerToBottom() {
  await nextTick();
  if (answerArea.value) answerArea.value.scrollTop = answerArea.value.scrollHeight;
}
</script>

<template>
  <main class="pet-window" :class="{ expanded }">
    <section v-if="expanded" class="chat-panel">
      <header class="panel-header" data-tauri-drag-region>
        <div>
          <p class="eyebrow">KnowRAG</p>
          <h1>问问我的知识库</h1>
        </div>
        <button class="close-button" type="button" aria-label="收起问答面板" @click="togglePanel">×</button>
      </header>

      <div class="status-line" :data-state="state">
        <span>{{ stateText[state] }}</span>
        <strong v-if="routeIntent">{{ routeText[routeIntent] || routeIntent }}</strong>
      </div>

      <div ref="answerArea" class="answer-area">
        <p v-if="!answer && !errorMessage" class="answer-placeholder">
          知识问题会检索已入库资料并列出引用，普通闲聊会直接回答。
        </p>
        <p v-if="answer" class="answer-text">{{ answer }}</p>
        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

        <section v-if="sources.length" class="sources">
          <h2>引用来源</h2>
          <details v-for="source in sources" :key="source.chunk_id" class="source-card">
            <summary>
              <span>[{{ source.citation }}] {{ source.document_title || source.source_path }}</span>
              <small>{{ Number(source.score || 0).toFixed(3) }}</small>
            </summary>
            <p class="source-meta">
              {{ (source.heading_path || []).join(" > ") || "无标题" }} ·
              L{{ source.start_line }}-{{ source.end_line }}
            </p>
            <p class="source-content">{{ source.content }}</p>
          </details>
        </section>
      </div>

      <form class="question-form" @submit.prevent="askQuestion">
        <textarea
          v-model="question"
          rows="2"
          maxlength="1000"
          placeholder="输入一个问题..."
          @keydown.enter.exact.prevent="askQuestion"
        />
        <button type="submit" :disabled="!question.trim() || state === 'thinking' || state === 'answering'">
          {{ state === "thinking" || state === "answering" ? "回答中" : "发送" }}
        </button>
      </form>
    </section>

    <section class="pet-side">
      <img
        class="pet-img"
        :src="petImage"
        alt="KnowRAG 小狗桌宠"
        draggable="false"
        @mousedown="onPetMouseDown"
        @contextmenu.prevent.stop="showContextMenu"
      />
    </section>
  </main>
</template>
