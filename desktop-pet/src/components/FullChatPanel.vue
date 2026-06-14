<script setup>
import { ref } from "vue";

const props = defineProps({
  messages: { type: Array, required: true },
  question: { type: String, required: true },
  state: { type: String, required: true },
  stateText: { type: Object, required: true },
  routeText: { type: Object, required: true },
});

const emit = defineEmits(["update:question", "submit", "close"]);

const messageArea = ref(null);

function submitQuestion() {
  emit("submit");
}

function updateQuestion(event) {
  emit("update:question", event.target.value);
}

defineExpose({
  scrollToBottom() {
    if (messageArea.value) messageArea.value.scrollTop = messageArea.value.scrollHeight;
  },
});
</script>

<template>
  <section class="full-chat visible">
    <header class="fc-header" data-tauri-drag-region>
      <span class="fc-title">桌宠助手 · 完整聊天</span>
      <button class="fc-close" type="button" aria-label="关闭" @click="emit('close')">✕</button>
    </header>

    <div ref="messageArea" class="fc-messages">
      <div v-if="messages.length === 0" class="fc-msg assistant">
        <div class="fc-avatar assistant-avatar">AI</div>
        <div class="fc-bubble">你好！欢迎来到完整聊天，这里可以连续对话，引用来源也能展开查看哦。</div>
      </div>

      <article v-for="message in messages" :key="message.id" class="fc-msg" :class="message.role">
        <div class="fc-avatar" :class="message.role === 'assistant' ? 'assistant-avatar' : 'user-avatar'">
          {{ message.role === "assistant" ? "AI" : "你" }}
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
            <summary>展开引用来源</summary>
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

    <form class="fc-input-row" @submit.prevent="submitQuestion">
      <input
        :value="question"
        class="fc-input"
        maxlength="500"
        placeholder="输入消息..."
        @input="updateQuestion"
        @keydown.enter.exact.prevent="submitQuestion"
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
</template>
