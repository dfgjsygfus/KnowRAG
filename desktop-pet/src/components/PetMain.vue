<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { LogicalPosition, LogicalSize } from "@tauri-apps/api/dpi";
import { listen } from "@tauri-apps/api/event";
import { Menu } from "@tauri-apps/api/menu";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";
import { getAllWindows, getCurrentWindow } from "@tauri-apps/api/window";

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
const messageArea = ref(null);
const petCanvas = ref(null);
const petShell = ref(null);
const petScale = ref(DEFAULT_PET_SCALE);
const particles = ref([]);
const isBouncing = ref(false);
const dragState = ref({ moved: false, startX: 0, startY: 0 });
const topK = 5;
let abortController = null;
let nextChatMessageIndex = 1;
let animationFrame = 0;
let bobPhase = 0;
let blinkTimer = 0;
let blinkDuration = 90;
let isBlinking = false;
let bounceAmount = 0;
let lastFrameTime = 0;
let particleId = 1;
let unlistenChatSubmit = null;
let unlistenChatClosed = null;
let unlistenPetMoved = null;

const SPRITE_W = 16;
const SPRITE_H = 16;
const PAL = [
  null,
  "#FAE3C6",
  "#E8C9A0",
  "#C4956A",
  "#5D3A1A",
  "#FFFFFF",
  "#FFB8B8",
  "#FF8B8B",
  "#8B5E3C",
];
const BASE_SPRITE = [
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,8,8,0,0,8,8,0,0,0,0,0,
  0,0,0,3,3,1,1,0,0,1,1,3,3,0,0,0,
  0,0,3,1,1,1,1,1,1,1,1,1,1,3,0,0,
  0,0,2,1,1,1,1,1,1,1,1,1,1,2,0,0,
  0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,
  0,0,1,1,4,4,1,1,1,4,4,1,1,1,0,0,
  0,0,1,1,4,5,4,1,1,4,5,4,1,1,0,0,
  0,0,1,1,4,4,1,1,1,4,4,1,1,1,0,0,
  0,0,1,6,1,1,1,1,1,1,1,1,6,1,0,0,
  0,0,1,1,1,1,4,4,4,4,1,1,1,1,0,0,
  0,0,1,1,1,1,4,5,5,4,1,1,1,1,0,0,
  0,0,1,1,1,1,1,7,7,1,1,1,1,1,0,0,
  0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,
  0,0,0,1,1,1,1,1,1,1,1,1,1,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
];

onMounted(() => {
  drawPet("normal");
  lastFrameTime = performance.now();
  animationFrame = requestAnimationFrame(tick);

  listen("pet-chat-submit", ({ payload }) => {
    isChatInputOpen.value = false;
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
});

onBeforeUnmount(() => {
  if (abortController) abortController.abort();
  if (animationFrame) cancelAnimationFrame(animationFrame);
  clearTimeout(hoverTimer);
  clearTimeout(danmakuFadeTimer);
  if (unlistenChatSubmit) unlistenChatSubmit();
  if (unlistenChatClosed) unlistenChatClosed();
  if (unlistenPetMoved) unlistenPetMoved();
  void closePetChatWindow();
});

const petStyle = computed(() => {
  const petSize = getPetSize(petScale.value);
  return {
    "--pet-size": `${petSize}px`,
    "--pet-shell-size": `${petSize + 36}px`,
    "--pet-bob-y": "0px",
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

const danmakuText = computed(() => {
  const msg = latestAssistantBubble.value;
  if (!msg) return "";
  if (msg.errorMessage) return msg.errorMessage;
  if (!msg.content) return "思考中...";
  const flat = msg.content.replace(/\s+/g, " ").trim();
  if (isAnswerLong.value) return flat.slice(0, DANMAKU_MAX_CHARS) + "…";
  return flat;
});

// ── Danmaku persistence: stays after closing light chat, fades after 10s ──
const danmakuVisible = ref(false);
const danmakuFading = ref(false);
let danmakuFadeTimer = null;

function showDanmaku() {
  clearTimeout(danmakuFadeTimer);
  danmakuFadeTimer = null;
  danmakuVisible.value = true;
  danmakuFading.value = false;
  if (chatSurface.value === "pet") {
    void resizeWindow();
  }
}

function scheduleDanmakuFadeOut() {
  if (!danmakuVisible.value) return;
  clearTimeout(danmakuFadeTimer);
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
  }, 10000);
}

function cancelDanmakuFade() {
  clearTimeout(danmakuFadeTimer);
  danmakuFadeTimer = null;
  danmakuFading.value = false;
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
  if (messageArea.value) messageArea.value.scrollTop = messageArea.value.scrollHeight;
}

function getSpriteForMood(mood) {
  const sprite = BASE_SPRITE.slice();
  if (mood === "blink") {
    [
      [6,4],[6,5],[6,9],[6,10],
      [7,4],[7,5],[7,6],[7,9],[7,10],[7,11],
      [8,4],[8,5],[8,9],[8,10],
    ].forEach(([row, col]) => {
      const index = row * SPRITE_W + col;
      if (sprite[index] === 4 || sprite[index] === 5) {
        sprite[index] = row === 7 && (col === 5 || col === 10) ? 4 : 1;
      }
    });
  }
  if (mood === "happy") {
    sprite[7 * SPRITE_W + 5] = 5;
    sprite[7 * SPRITE_W + 10] = 5;
    sprite[12 * SPRITE_W + 7] = 7;
    sprite[12 * SPRITE_W + 8] = 7;
  }
  return sprite;
}

function drawPet(mood) {
  const canvas = petCanvas.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const sprite = getSpriteForMood(mood);
  ctx.clearRect(0, 0, SPRITE_W, SPRITE_H);
  for (let i = 0; i < SPRITE_W * SPRITE_H; i += 1) {
    const colorIndex = sprite[i];
    if (!colorIndex) continue;
    ctx.fillStyle = PAL[colorIndex];
    ctx.fillRect(i % SPRITE_W, Math.floor(i / SPRITE_W), 1, 1);
  }
}

function tick(now) {
  const dt = Math.min((now - lastFrameTime) / 1000, 0.2);
  lastFrameTime = now;

  bobPhase = (bobPhase + dt * 3) % (Math.PI * 2);
  if (bounceAmount > 0) bounceAmount = Math.max(0, bounceAmount - dt * 4);
  isBouncing.value = bounceAmount > 0;

  blinkTimer += dt * 60;
  if (blinkTimer > blinkDuration) {
    isBlinking = !isBlinking;
    blinkTimer = 0;
    blinkDuration = isBlinking ? 3 + Math.random() * 5 : 60 + Math.random() * 180;
  }

  const canvas = petCanvas.value;
  if (canvas) {
    const bobY = Math.sin(bobPhase) * 2 - bounceAmount * 14;
    canvas.closest(".pet-shell")?.style.setProperty("--pet-bob-y", `${bobY}px`);
  }

  drawPet(isBlinking ? "blink" : bounceAmount > 0.3 ? "happy" : "normal");
  animationFrame = requestAnimationFrame(tick);
}

function bouncePet() {
  bounceAmount = 1;
  spawnParticle("💗");
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
        'light-answer-typing': !latestAssistantBubble?.content && !latestAssistantBubble?.errorMessage,
        'light-answer-long': isAnswerLong,
        'danmaku-fading': danmakuFading,
      }"
      @click="isAnswerLong ? expandToFullFromDanmaku() : undefined"
    >
      <span class="light-answer-text">{{ danmakuText }}</span>
      <span v-if="isAnswerLong" class="light-answer-expand">展开全文 →</span>
    </span>

    <!-- ── Full chat panel (only visible in full mode) ── -->
    <section v-if="chatSurface === 'full'" class="full-chat visible">
      <header class="fc-header" data-tauri-drag-region>
        <span class="fc-title">🐶 旺财 · 完整聊天</span>
        <button class="fc-close" type="button" aria-label="关闭" @click="closeToPet">✕</button>
      </header>

      <div ref="messageArea" class="fc-messages">
        <div v-if="messages.length === 0" class="fc-msg assistant">
          <div class="fc-avatar assistant-avatar">🐶</div>
          <div class="fc-bubble">汪！欢迎来到完整聊天，这里可以连续对话，引用来源也能展开查看哦。</div>
        </div>

        <article v-for="message in messages" :key="message.id" class="fc-msg" :class="message.role">
          <div class="fc-avatar" :class="message.role === 'assistant' ? 'assistant-avatar' : 'user-avatar'">
            {{ message.role === "assistant" ? "🐶" : "👤" }}
          </div>
          <div class="fc-bubble-wrap">
            <div class="fc-bubble">
              <p v-if="message.role === 'user'" class="fc-text">{{ message.content }}</p>

              <template v-else>
                <p v-if="message.content" class="fc-text">{{ message.content }}</p>
                <p v-else-if="message.errorMessage" class="fc-text fc-error">{{ message.errorMessage }}</p>
                <p v-else class="fc-text fc-typing">{{ stateText[message.status] || "正在处理..." }}</p>
                <p v-if="message.content && message.errorMessage" class="fc-text fc-error follow-up-error">
                  {{ message.errorMessage }}
                </p>
              </template>
            </div>

            <div v-if="message.role === 'assistant' && (message.routeIntent || message.sources?.length)" class="fc-meta">
              <span v-if="message.routeIntent">{{ routeText[message.routeIntent] || message.routeIntent }}</span>
              <span v-if="message.sources?.length">引用 {{ message.sources.length }} 条</span>
            </div>

            <details v-if="message.role === 'assistant' && message.sources?.length" class="fc-refs">
              <summary>📚 展开引用来源</summary>
              <div class="fc-refs-body">
                <div v-for="source in message.sources" :key="source.chunk_id" class="fc-ref-item">
                  <strong>[{{ source.citation }}] {{ source.document_title || source.source_path }}</strong>
                  <small>{{ Number(source.score || 0).toFixed(3) }}</small>
                  <p>
                    {{ (source.heading_path || []).join(" > ") || "无标题" }} ·
                    L{{ source.start_line }}-{{ source.end_line }}
                  </p>
                  <p>{{ source.content }}</p>
                </div>
              </div>
            </details>
          </div>
        </article>
      </div>

      <form class="fc-input-row" @submit.prevent="askQuestion">
        <input
          v-model="question"
          class="fc-input"
          maxlength="500"
          placeholder="输入消息..."
          @keydown.enter.exact.prevent="askQuestion"
        />
        <button
          class="fc-send"
          type="submit"
          :disabled="!question.trim() || state === 'thinking' || state === 'answering'"
        >
          发送
        </button>
      </form>
    </section>

    <!-- ── Pet (always visible — single persistent canvas, never destroyed) ── -->
    <section class="pet-side" :style="petStyle">
      <div
        ref="petShell"
        class="pet-shell"
        :class="{ bouncing: isBouncing, thinking: isWorking, error: isFailure, empty: isNoResult }"
        role="button"
        aria-label="KnowRAG 像素小狗桌宠"
        tabindex="0"
        @mousedown="onPetMouseDown($event)"
        @click="onPetClick"
        @contextmenu.prevent.stop="openContextMenu"
        @mouseenter="onPetEnter"
        @mouseleave="onPetLeave"
      >
        <div class="pet-inner">
          <canvas ref="petCanvas" class="pet-canvas" width="16" height="16"></canvas>
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
