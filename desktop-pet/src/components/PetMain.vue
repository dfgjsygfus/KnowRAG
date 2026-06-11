<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { LogicalPosition, LogicalSize } from "@tauri-apps/api/dpi";
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
import { createPetContextMenu, showPetContextMenu } from "../lib/petContextMenu";
import {
  DEFAULT_PET_SCALE,
  getNextPetScale,
  getPetAnchorOffset,
  getPetSize,
  getPetWindowSize,
  getPositionKeepingPetAnchor,
} from "../lib/petScale";

const chatSurface = ref("pet"); // "pet" | "bubble" | "full"
const question = ref("");
const messages = ref([]);
const state = ref("idle");
const messageArea = ref(null);
const bubbleMessageArea = ref(null);
const petCanvas = ref(null);
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
});

onBeforeUnmount(() => {
  if (abortController) abortController.abort();
  if (animationFrame) cancelAnimationFrame(animationFrame);
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
  thinking: "正在判断问题意图...",
  answering: "正在组织答案...",
  empty: "资料里暂时没有找到答案。",
  error: "问答服务发生错误。",
};

const routeText = {
  knowledge_query: "知识库问答",
  casual_chat: "普通闲聊",
};

const bubbleMessages = computed(() => {
  const all = messages.value;
  if (all.length === 0) return [];

  const result = [];
  for (let i = all.length - 1; i >= 0; i--) {
    const msg = all[i];
    result.unshift(msg);
    if (msg.role === "user") break;
  }
  return result;
});

const bubbleEmptyState = computed(() => bubbleMessages.value.length === 0);

async function setChatSurface(surface) {
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

    chatSurface.value = surface;

    const newSize = getPetWindowSize(surface, petScale.value);
    const newAnchor = getPetAnchorOffset(surface, petScale.value, newSize);

    nextPosition = getPositionKeepingPetAnchor(oldPosition, oldAnchor, newAnchor);
  } catch {
    chatSurface.value = surface;
  }

  await resizeWindow(nextPosition);
  if (surface === "full") await scrollMessagesToBottom();
}

async function toggleChat() {
  await setChatSurface(chatSurface.value === "pet" ? "bubble" : "pet");
}

async function openBubbleChat() {
  if (chatSurface.value !== "pet") return;
  bouncePet();
  await setChatSurface("bubble");
}

async function expandToFull() {
  await setChatSurface("full");
}

async function closeToPet() {
  await setChatSurface("pet");
}

async function resizeWindow(nextPosition) {
  try {
    const window = getCurrentWindow();
    const size = getPetWindowSize(chatSurface.value, petScale.value);

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

    const newSize = getPetWindowSize(surface, nextScale);
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
      chatSurface: chatSurface.value,
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
  openBubbleChat();
}

async function askQuestion() {
  const normalized = question.value.trim();
  if (!normalized || state.value === "thinking" || state.value === "answering") return;

  if (abortController) abortController.abort();
  abortController = new AbortController();

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
  }
  if (event === "delta") {
    messages.value = appendAssistantDelta(messages.value, messageId, data.content || "");
    scrollMessagesToBottom();
  }
  if (event === "done") {
    state.value = data.state || "success";
    messages.value = updateAssistantMessage(messages.value, messageId, {
      status: data.state || "success",
    });
  }
  if (event === "error") {
    state.value = "error";
    messages.value = updateAssistantMessage(messages.value, messageId, {
      status: "error",
      errorMessage: data.message || "问答服务发生错误。",
    });
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
  if (bubbleMessageArea.value) bubbleMessageArea.value.scrollTop = bubbleMessageArea.value.scrollHeight;
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
  <main class="pet-window" :class="chatSurface">
    <section v-if="chatSurface === 'bubble'" class="short-chat arrow-right">
      <div class="sc-header">
        <span class="sc-header-title">🐶 旺财 · 轻聊</span>
        <div class="sc-header-actions">
          <button class="sc-btn expand-btn" type="button" title="展开完整聊天" @click="expandToFull">⤢</button>
          <button class="sc-btn" type="button" title="关闭" @click="closeToPet">✕</button>
        </div>
      </div>

      <div ref="bubbleMessageArea" class="sc-messages">
        <div v-if="bubbleEmptyState" class="sc-msg assistant">
          <div class="sc-bubble">汪！有什么想问的？</div>
        </div>

        <div v-for="message in bubbleMessages" :key="message.id" class="sc-msg" :class="message.role">
          <div v-if="message.role === 'user'" class="sc-bubble">{{ message.content }}</div>

          <template v-else>
            <div v-if="message.content" class="sc-bubble">{{ message.content }}</div>
            <div v-else-if="message.errorMessage" class="sc-bubble sc-error">{{ message.errorMessage }}</div>
            <div v-else class="sc-bubble sc-typing">{{ stateText[message.status] || "正在处理..." }}</div>
            <div v-if="message.content && message.errorMessage" class="sc-bubble sc-error follow-up-error">
              {{ message.errorMessage }}
            </div>

            <div v-if="message.routeIntent || message.sources?.length" class="kb-info">
              <span v-if="message.routeIntent">{{ routeText[message.routeIntent] || message.routeIntent }}</span>
              <span v-if="message.sources?.length">引用 {{ message.sources.length }} 条</span>
            </div>
          </template>
        </div>
      </div>

      <form class="sc-input-row" @submit.prevent="askQuestion">
        <input
          v-model="question"
          class="sc-input"
          maxlength="200"
          placeholder="问一句..."
          @keydown.enter.exact.prevent="askQuestion"
        />
        <button
          class="sc-send"
          type="submit"
          :disabled="!question.trim() || state === 'thinking' || state === 'answering'"
        >
          ➤
        </button>
      </form>
    </section>

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

    <section class="pet-side" :style="petStyle">
      <div
        class="pet-shell"
        :class="{ bouncing: isBouncing }"
        role="button"
        aria-label="KnowRAG 像素小狗桌宠"
        tabindex="0"
        @mousedown="onPetMouseDown($event)"
        @click="onPetClick"
        @contextmenu.prevent.stop="openContextMenu"
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
  </main>
</template>
