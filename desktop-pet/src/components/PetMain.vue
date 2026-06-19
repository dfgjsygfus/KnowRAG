<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { LogicalPosition, LogicalSize } from "@tauri-apps/api/dpi";
import { listen } from "@tauri-apps/api/event";
import { Menu } from "@tauri-apps/api/menu";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";
import { getAllWindows, getCurrentWindow } from "@tauri-apps/api/window";

import { PET_FRAME_INTERVAL_MS, getPetAnimationFrames } from "../lib/petAnimationFrames";
import FullChatPanel from "./FullChatPanel.vue";
import { openAdminWindow } from "../lib/adminWindow";
import { exitDesktopPet } from "../lib/appLifecycle";
import {
  appendAssistantDelta,
  createAssistantMessage,
  createUserMessage,
  updateAssistantMessage,
} from "../lib/chatMessages";
import { streamQuestion } from "../lib/chatStream";
import { closePetChatWindow, openPetChatWindow, positionPetChatWindow } from "../lib/petChatWindow";
import { createPetContextMenu, showPetContextMenu } from "../lib/petContextMenu";
import { computeDanmakuLifespan } from "../lib/danmakuTiming";
import {
  DEFAULT_PET_SCALE,
  getNextPetScale,
  getPetAnchorOffset,
  getPetSize,
  getPetWindowSize,
  getPositionKeepingPetAnchor,
} from "../lib/petScale";

const chatSurface = ref("pet"); // "pet" | "full"
const isChatInputOpen = ref(false);
const question = ref("");
const messages = ref([]);
const state = ref("idle");
const fullChatPanel = ref(null);
const petShell = ref(null);
const petScale = ref(DEFAULT_PET_SCALE);
const particles = ref([]);
const isBouncing = ref(false);
const petFrameIndex = ref(0);
const dragState = ref({ moved: false, startX: 0, startY: 0 });
const topK = 5;
let abortController = null;
let nextChatMessageIndex = 1;
let particleId = 1;
let bounceTimer = null;
let petFrameTimer = null;
let unlistenChatSubmit = null;
let unlistenChatClosed = null;
let unlistenPetMoved = null;
let danmakuResizeObserver = null;

onMounted(() => {
  petFrameTimer = window.setInterval(() => {
    const frames = getPetAnimationFrames(isWorking.value);
    petFrameIndex.value = (petFrameIndex.value + 1) % frames.length;
  }, PET_FRAME_INTERVAL_MS);

  listen("pet-chat-submit", ({ payload }) => {
    void askQuestion(payload?.question || "");
  }).then((unlisten) => {
    unlistenChatSubmit = unlisten;
  }).catch(() => {
    // Browser dev mode has no Tauri event bus.
  });

  listen("pet-chat-closed", () => {
    isChatInputOpen.value = false;
  }).then((unlisten) => {
    unlistenChatClosed = unlisten;
  }).catch(() => {
    // Browser dev mode has no Tauri event bus.
  });

  try {
    getCurrentWindow().onMoved(() => {
      if (isChatInputOpen.value) void positionChatInput();
    }).then((unlisten) => {
      unlistenPetMoved = unlisten;
    }).catch(() => {
      // Browser dev mode has no native window move events.
    });
  } catch {
    // Browser dev mode has no native window API.
  }

  if (typeof ResizeObserver !== "undefined") {
    danmakuResizeObserver = new ResizeObserver(() => {
      void updateDanmakuOverflow();
    });
    if (danmakuTextRef.value) {
      danmakuResizeObserver.observe(danmakuTextRef.value);
    }
  }
});

onBeforeUnmount(() => {
  if (abortController) abortController.abort();
  clearTimeout(bounceTimer);
  clearInterval(petFrameTimer);
  clearTimeout(hoverTimer);
  clearTimeout(danmakuFadeTimer);
  if (unlistenChatSubmit) unlistenChatSubmit();
  if (unlistenChatClosed) unlistenChatClosed();
  if (unlistenPetMoved) unlistenPetMoved();
  if (danmakuResizeObserver) danmakuResizeObserver.disconnect();
  void closePetChatWindow();
});

const petStyle = computed(() => {
  const petSize = getPetSize(petScale.value);
  return {
    "--pet-size": `${petSize}px`,
    "--pet-shell-size": `${petSize + 36}px`,
  };
});

const stateText = {
  idle: "准备好了",
  thinking: "正在判断问题意图...",
  answering: "正在组织答案...",
  empty: "资料里暂时没有找到答案。",
  error: "问答服务发生错误。",
};

const routeText = {
  knowledge_query: "知识库问答",
  casual_chat: "普通闲聊",
};

const isWorking = computed(() => ["thinking", "answering"].includes(state.value));
const isFailure = computed(() => ["error"].includes(state.value));
const isNoResult = computed(() => ["empty"].includes(state.value));
const petAnimationFrames = computed(() => getPetAnimationFrames(isWorking.value));
const petFrameImage = computed(() => petAnimationFrames.value[petFrameIndex.value % petAnimationFrames.value.length]);

watch(isWorking, () => {
  petFrameIndex.value = 0;
});

// ── Hover bubble (shown below pet in idle mode) ──
const hoverBubble = ref(false);
let hoverTimer = null;

function onPetEnter() {
  if (chatSurface.value !== "pet" || isChatInputOpen.value) return;
  clearTimeout(hoverTimer);
  hoverTimer = setTimeout(() => {
    hoverBubble.value = true;
  }, 400);
}
function onPetLeave() {
  if (chatSurface.value !== "pet") return;
  clearTimeout(hoverTimer);
  hoverTimer = setTimeout(() => {
    hoverBubble.value = false;
  }, 600);
}
function onBubbleEnter() {
  clearTimeout(hoverTimer); // keep bubble visible while hovering it
}
function onBubbleLeave() {
  hoverTimer = setTimeout(() => {
    hoverBubble.value = false;
  }, 300);
}

const DANMAKU_MAX_CHARS = 150;

const latestAssistantBubble = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i];
    if (msg.role === "assistant") return msg;
  }
  return null;
});

const isAnswerLong = computed(() => {
  const content = latestAssistantBubble.value?.content || "";
  return content.length > DANMAKU_MAX_CHARS;
});

const isTyping = computed(() => {
  const msg = latestAssistantBubble.value;
  return !!msg && !msg.content && !msg.errorMessage;
});

const danmakuText = computed(() => {
  const msg = latestAssistantBubble.value;
  if (!msg) return "";
  if (msg.errorMessage) return msg.errorMessage;
  if (!msg.content) return "思考中";
  const flat = msg.content.replace(/\s+/g, " ").trim();
  if (isAnswerLong.value) return flat.slice(0, DANMAKU_MAX_CHARS) + "…";
  return flat;
});

// ── Danmaku persistence: stays after closing light chat, fades after a content-aware delay ──
const danmakuVisible = ref(false);
const danmakuFading = ref(false);
const danmakuTextRef = ref(null);
const isDanmakuTextOverflowing = ref(false);
const isDanmakuExpandable = computed(() => isAnswerLong.value || isDanmakuTextOverflowing.value);
let danmakuFadeTimer = null;
let danmakuLifespanMs = 0;
let danmakuFadeDeadline = 0;
let danmakuRemainingMs = 0;
let danmakuHovering = false;

function showDanmaku() {
  clearTimeout(danmakuFadeTimer);
  danmakuFadeTimer = null;
  danmakuVisible.value = true;
  danmakuFading.value = false;
  if (chatSurface.value === "pet") {
    void resizeWindow();
  }
  void updateDanmakuOverflow();
}

function updateDanmakuOverflow() {
  const el = danmakuTextRef.value;
  if (!el) {
    isDanmakuTextOverflowing.value = false;
    return;
  }
  isDanmakuTextOverflowing.value = el.scrollHeight > el.clientHeight + 1;
}

function scheduleDanmakuFadeOut() {
  if (!danmakuVisible.value) return;
  const content = latestAssistantBubble.value?.content
    || latestAssistantBubble.value?.errorMessage
    || "";
  danmakuLifespanMs = computeDanmakuLifespan(content);
  danmakuRemainingMs = danmakuLifespanMs;
  if (danmakuHovering) {
    clearTimeout(danmakuFadeTimer);
    danmakuFadeTimer = null;
    return;
  }
  startDanmakuFadeTimer(danmakuLifespanMs);
}

function startDanmakuFadeTimer(delayMs) {
  clearTimeout(danmakuFadeTimer);
  danmakuFadeDeadline = Date.now() + delayMs;
  danmakuFadeTimer = setTimeout(() => {
    danmakuFading.value = true;
    // After CSS transition, hide and clean up (only if still in pet mode)
    danmakuFadeTimer = setTimeout(() => {
      danmakuVisible.value = false;
      danmakuFading.value = false;
      if (chatSurface.value === "pet") {
        messages.value = [];
        void resizeWindow();
      }
    }, 700);
  }, delayMs);
}

function cancelDanmakuFade() {
  clearTimeout(danmakuFadeTimer);
  danmakuFadeTimer = null;
  danmakuFading.value = false;
  danmakuRemainingMs = 0;
  danmakuFadeDeadline = 0;
}

function onDanmakuEnter() {
  danmakuHovering = true;
  if (danmakuFadeTimer && danmakuFadeDeadline) {
    danmakuRemainingMs = Math.max(0, danmakuFadeDeadline - Date.now());
  }
  clearTimeout(danmakuFadeTimer);
  danmakuFadeTimer = null;
  danmakuFading.value = false;
}

function onDanmakuLeave() {
  danmakuHovering = false;
  if (!danmakuVisible.value) return;
  const delay = danmakuRemainingMs > 0 ? danmakuRemainingMs : danmakuLifespanMs;
  startDanmakuFadeTimer(delay);
}

function windowSizeOptions(surface = chatSurface.value) {
  return {
    reserveFloatingAnswer: surface === "pet" && danmakuVisible.value,
  };
}

// Watch for new assistant bubble → show danmaku
watch(() => latestAssistantBubble.value, (bubble) => {
  if (bubble) showDanmaku();
});

watch(danmakuTextRef, (el) => {
  if (danmakuResizeObserver) {
    danmakuResizeObserver.disconnect();
    if (el) danmakuResizeObserver.observe(el);
  }
  void updateDanmakuOverflow();
});

watch([danmakuText, chatSurface], () => {
  void updateDanmakuOverflow();
});

async function setChatSurface(surface) {
  if (surface === "light") {
    await openChatInput();
    return;
  }
  if (surface === chatSurface.value) return;

  // Capture old state before changing chatSurface so we can compute the
  // pet-anchor-based position delta.
  const oldSurface = chatSurface.value;
  const oldScale = petScale.value;
  let nextPosition;

  try {
    const window = getCurrentWindow();
    const scaleFactor = await window.scaleFactor();
    const oldPosition = (await window.outerPosition()).toLogical(scaleFactor);
    const oldSize = (await window.outerSize()).toLogical(scaleFactor);

    const oldAnchor = getPetAnchorOffset(oldSurface, oldScale, oldSize);

    // Compute new window size from the target surface.
    const newSize = getPetWindowSize(surface, petScale.value, windowSizeOptions(surface));
    const newAnchor = getPetAnchorOffset(surface, petScale.value, newSize);
    nextPosition = getPositionKeepingPetAnchor(oldPosition, oldAnchor, newAnchor);

    chatSurface.value = surface;

    // ── Danmaku & message lifecycle ──
    if (surface === "full") {
      await closeChatInput();
      cancelDanmakuFade();
      danmakuVisible.value = false;
    }

    await resizeWindow(nextPosition, newSize);
  } catch {
    chatSurface.value = surface;
    try { await resizeWindow(); } catch { /* ignore */ }
  }

  if (surface === "full") await scrollMessagesToBottom();
}

async function toggleChat() {
  if (isChatInputOpen.value) {
    await closeChatInput();
  } else if (chatSurface.value === "pet") {
    await openChatInput();
  } else {
    await setChatSurface("pet");
  }
}

async function openChatInput() {
  if (chatSurface.value !== "pet") {
    await setChatSurface("pet");
  }
  hoverBubble.value = false;
  try {
    await openPetChatWindow({
      WebviewWindowClass: WebviewWindow,
      currentWindow: getCurrentWindow(),
      petScale: petScale.value,
      petBounds: petShell.value?.getBoundingClientRect(),
    });
    isChatInputOpen.value = true;
  } catch (error) {
    appendSystemError(error.message || "无法打开输入框。");
  }
}

async function positionChatInput() {
  try {
    await positionPetChatWindow({
      WebviewWindowClass: WebviewWindow,
      currentWindow: getCurrentWindow(),
      petScale: petScale.value,
      petBounds: petShell.value?.getBoundingClientRect(),
      bringToFront: true,
    });
  } catch {
    // The standalone input window may have been closed independently.
  }
}

async function closeChatInput() {
  try {
    await closePetChatWindow(WebviewWindow);
  } catch {
    // The standalone input window may already be gone.
  }
  isChatInputOpen.value = false;
  hoverBubble.value = false;
}

async function expandToFull() {
  await setChatSurface("full");
}

async function expandToFullFromDanmaku() {
  await setChatSurface("full");
}

async function closeToPet() {
  await closeChatInput();
  await setChatSurface("pet");
}

async function resizeWindow(nextPosition, nextSize) {
  try {
    const window = getCurrentWindow();
    const size = nextSize || getPetWindowSize(chatSurface.value, petScale.value, windowSizeOptions());

    let position;
    if (nextPosition) {
      position = nextPosition;
    } else {
      const scaleFactor = await window.scaleFactor();
      const oldPosition = (await window.outerPosition()).toLogical(scaleFactor);
      const oldSize = (await window.outerSize()).toLogical(scaleFactor);
      position = getPositionKeepingPetAnchor(
        oldPosition,
        getPetAnchorOffset(chatSurface.value, petScale.value, oldSize),
        getPetAnchorOffset(chatSurface.value, petScale.value, size),
      );
    }

    await window.setSize(new LogicalSize(size.width, size.height));
    await window.setPosition(new LogicalPosition(position.x, position.y));
  } catch {
    // Running in a regular browser during UI development.
  }
}

async function setPetScale(nextScale) {
  // Capture old state before changing scale so we can compute the
  // pet-anchor-based position delta.
  const oldScale = petScale.value;
  const surface = chatSurface.value;
  let nextPosition;

  try {
    const window = getCurrentWindow();
    const scaleFactor = await window.scaleFactor();
    const oldPosition = (await window.outerPosition()).toLogical(scaleFactor);
    const oldSize = (await window.outerSize()).toLogical(scaleFactor);

    const oldAnchor = getPetAnchorOffset(surface, oldScale, oldSize);

    petScale.value = nextScale;

    const newSize = getPetWindowSize(surface, nextScale, windowSizeOptions(surface));
    const newAnchor = getPetAnchorOffset(surface, nextScale, newSize);

    nextPosition = getPositionKeepingPetAnchor(oldPosition, oldAnchor, newAnchor);
  } catch {
    petScale.value = nextScale;
  }

  await resizeWindow(nextPosition);
}

async function scalePetUp() {
  await setPetScale(getNextPetScale(petScale.value, 1));
}

async function scalePetDown() {
  await setPetScale(getNextPetScale(petScale.value, -1));
}

async function resetPetScale() {
  await setPetScale(DEFAULT_PET_SCALE);
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
    appendSystemError(error.message || "无法打开 KnowRAG 管理台。");
  }
}

async function openContextMenu(e) {
  e.preventDefault();
  e.stopPropagation();

  try {
    const menu = await createPetContextMenu(Menu, {
      openAdmin: openManagement,
      toggleChat,
      openFull: () => setChatSurface("full"),
      setScale: setPetScale,
      exitPet,
    }, {
      chatSurface: isChatInputOpen.value ? "light" : chatSurface.value,
      petScale: petScale.value,
    });
    await showPetContextMenu(menu);
  } catch (error) {
    appendSystemError(error.message || "无法打开桌宠菜单。");
  }

}

function onPetMouseDown(e) {
  if (e.button !== 0) return; // only left-click drag
  dragState.value = { moved: false, startX: e.clientX, startY: e.clientY };

  const onMove = (ev) => {
    if (Math.abs(ev.clientX - dragState.value.startX) > 3 ||
        Math.abs(ev.clientY - dragState.value.startY) > 3) {
      dragState.value.moved = true;
    }
  };
  const onUp = () => {
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
  };
  document.addEventListener("pointermove", onMove);
  document.addEventListener("pointerup", onUp, { once: true });

  getCurrentWindow().startDragging().catch(() => {});
}

function onPetClick() {
  if (dragState.value.moved) {
    dragState.value.moved = false;
    return;
  }
  if (chatSurface.value === "pet") {
    bouncePet();
    openChatInput();
  } else {
    closeToPet();
  }
}

async function askQuestion(rawQuestion = question.value) {
  const normalized = rawQuestion.trim();
  if (!normalized || state.value === "thinking" || state.value === "answering") return;

  if (abortController) abortController.abort();
  abortController = new AbortController();

  // Pet-mode quick asks are one-shot; full mode keeps the conversation history.
  if (chatSurface.value !== "full") {
    messages.value = [];
  }

  const userMessage = createUserMessage(nextMessageId("u"), normalized);
  const assistantMessage = createAssistantMessage(nextMessageId("a"));
  messages.value = [...messages.value, userMessage, assistantMessage];
  state.value = "thinking";

  question.value = "";
  bouncePet();
  await scrollMessagesToBottom();

  try {
    await streamQuestion(
      normalized,
      topK,
      (event, data) => handleStreamEvent(assistantMessage.id, event, data),
      fetch,
      abortController.signal,
    );
  } catch (error) {
    if (error.name === "AbortError") return;
    state.value = "error";
    messages.value = updateAssistantMessage(messages.value, assistantMessage.id, {
      status: "error",
      errorMessage: error.message || "无法连接 KnowRAG 后端。",
    });
    if (chatSurface.value === "pet") scheduleDanmakuFadeOut();
    await scrollMessagesToBottom();
  } finally {
    if (abortController && !abortController.signal.aborted) abortController = null;
  }
}

function handleStreamEvent(messageId, event, data) {
  if (event === "status") {
    state.value = data.state || state.value;
    messages.value = updateAssistantMessage(messages.value, messageId, {
      status: data.state || state.value,
    });
  }
  if (event === "routing") {
    messages.value = updateAssistantMessage(messages.value, messageId, {
      routeIntent: data.intent || "",
    });
  }
  if (event === "sources") {
    messages.value = updateAssistantMessage(messages.value, messageId, {
      sources: data.sources || [],
    });
    if (!(data.sources || []).length && state.value !== "error") {
      state.value = "empty";
    }
  }
  if (event === "delta") {
    state.value = "answering";
    messages.value = appendAssistantDelta(messages.value, messageId, data.content || "");
    scrollMessagesToBottom();
  }
  if (event === "done") {
    state.value = data.state || "success";
    messages.value = updateAssistantMessage(messages.value, messageId, {
      status: data.state || "success",
    });
    if (chatSurface.value === "pet") scheduleDanmakuFadeOut();
  }
  if (event === "error") {
    state.value = "error";
    messages.value = updateAssistantMessage(messages.value, messageId, {
      status: "error",
      errorMessage: data.message || "问答服务发生错误。",
    });
    if (chatSurface.value === "pet") scheduleDanmakuFadeOut();
  }
}

function appendSystemError(message) {
  messages.value = [
    ...messages.value,
    {
      ...createAssistantMessage(nextMessageId("a")),
      status: "error",
      errorMessage: message,
    },
  ];
  state.value = "error";
  scrollMessagesToBottom();
}

function nextMessageId(prefix) {
  const id = `${prefix}${nextChatMessageIndex}`;
  nextChatMessageIndex += 1;
  return id;
}

async function scrollMessagesToBottom() {
  await nextTick();
  fullChatPanel.value?.scrollToBottom?.();
}

function bouncePet() {
  clearTimeout(bounceTimer);
  isBouncing.value = true;
  bounceTimer = window.setTimeout(() => {
    isBouncing.value = false;
  }, 520);
  spawnParticle("✦");
}

function spawnParticle(label) {
  const id = particleId;
  particleId += 1;
  particles.value = [...particles.value, { id, label }];
  window.setTimeout(() => {
    particles.value = particles.value.filter((particle) => particle.id !== id);
  }, 1600);
}
</script>

<template>
  <main class="pet-window" :class="chatSurface" :style="petStyle">
    <!-- ── Floating danmaku answer (persists after closing light chat) ── -->
    <span
      v-show="danmakuVisible && chatSurface !== 'full'"
      class="light-answer-float"
      :class="{
        'light-answer-error': latestAssistantBubble?.errorMessage,
        'light-answer-typing': isTyping,
        'light-answer-long': isDanmakuExpandable,
        'danmaku-fading': danmakuFading,
      }"
      @mouseenter="onDanmakuEnter"
      @mouseleave="onDanmakuLeave"
      @click="isDanmakuExpandable ? expandToFullFromDanmaku() : undefined"
    >
      <span ref="danmakuTextRef" class="light-answer-text">
        {{ danmakuText }}
        <span v-if="isTyping" class="typing-dots" aria-hidden="true">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </span>
      </span>
      <span v-if="isDanmakuExpandable" class="light-answer-expand">展开全文 →</span>
    </span>

    <!-- ── Full chat panel (only visible in full mode) ── -->
    <FullChatPanel
      v-if="chatSurface === 'full'"
      ref="fullChatPanel"
      v-model:question="question"
      :messages="messages"
      :state="state"
      :state-text="stateText"
      :route-text="routeText"
      @submit="askQuestion"
      @close="closeToPet"
    />

    <!-- ── Pet (always visible — persistent frame image, never destroyed) ── -->
    <section class="pet-side" :style="petStyle">
      <div
        ref="petShell"
        class="pet-shell"
        :class="{
          idle: !isWorking && !isFailure && !isNoResult,
          bouncing: isBouncing,
          thinking: isWorking,
          error: isFailure,
          empty: isNoResult,
        }"
        role="button"
        aria-label="KnowRAG 桌宠"
        tabindex="0"
        @mousedown="onPetMouseDown($event)"
        @click="onPetClick"
        @contextmenu.prevent.stop="openContextMenu"
        @mouseenter="onPetEnter"
        @mouseleave="onPetLeave"
      >
        <div class="pet-inner">
          <img class="pet-character" :src="petFrameImage" alt="" draggable="false" />
          <div class="pet-shadow"></div>
        </div>
        <div class="pet-particles">
          <span v-for="particle in particles" :key="particle.id" class="pet-particle">{{ particle.label }}</span>
        </div>
      </div>
    </section>

    <!-- ── Faint hover bubble shortcut (pet mode only, relative to window) ── -->
    <div
      v-show="chatSurface === 'pet' && !isChatInputOpen"
      class="pet-hover-bubble"
      :class="{ visible: hoverBubble }"
      @mouseenter="onBubbleEnter"
      @mouseleave="onBubbleLeave"
      @click.stop="setChatSurface('light')"
    >💬 问一问</div>
  </main>
</template>
