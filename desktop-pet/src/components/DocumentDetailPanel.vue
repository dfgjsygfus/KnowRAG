<script setup>
import { computed, ref, watch } from "vue";

import { renderMarkdown } from "../lib/markdown.js";
import { fileExt, formatSize } from "../lib/format.js";
import { useAdminApi } from "../composables/useAdminApi.js";
import { useToast } from "../composables/useToast.js";

const props = defineProps({
  document: { type: Object, required: true },
});

defineEmits(["close"]);

const api = useAdminApi();
const { showToast } = useToast();
const current = ref({ ...props.document });
const isLoading = ref(false);
let requestId = 0;

watch(
  () => props.document,
  (doc) => {
    current.value = { ...doc };
    if (!doc.content) {
      void loadContent();
    }
  },
  { immediate: true },
);

async function loadContent() {
  const id = current.value.id;
  requestId += 1;
  const thisRequest = requestId;
  isLoading.value = true;
  try {
    const detail = await api.fetchDocument(id);
    if (thisRequest !== requestId) return;
    current.value = { ...current.value, ...detail };
  } catch (error) {
    if (thisRequest !== requestId) return;
    showToast(error.message || "读取详情失败");
  } finally {
    if (thisRequest === requestId) {
      isLoading.value = false;
    }
  }
}

const renderedContent = computed(() => renderMarkdown(current.value.content || ""));
</script>

<template>
  <div class="detail-card section-card">
    <div class="section-card-header">
      <h2>{{ current.filename }}</h2>
      <div style="display: flex; align-items: center; gap: 12px;">
        <span class="detail-meta">{{ current.updated_at || current.created_at }} · {{ formatSize(current.size) }}</span>
        <button class="detail-close" title="关闭预览" @click="$emit('close')">✕</button>
      </div>
    </div>

    <div v-if="current.status === 'ready'" class="result-grid">
      <div class="result-item"><b>{{ current.sections_count }}</b><span>Sections</span></div>
      <div class="result-item"><b>{{ current.chunks_count }}</b><span>Chunks</span></div>
      <div class="result-item"><b>{{ current.vectors_count }}</b><span>Vectors</span></div>
      <div class="result-item"><b>{{ current.stored_count }}</b><span>Stored</span></div>
      <div class="result-item"><b>{{ (current.chunks || []).length }}</b><span>Saved Chunks</span></div>
    </div>

    <div class="detail-panel">
      <div class="detail-header">
        <span>原文预览</span>
        <span class="detail-meta">{{ fileExt(current.filename).toUpperCase() }}</span>
      </div>
      <div v-if="isLoading" class="markdown-body">加载中…</div>
      <div v-else class="markdown-body" v-html="renderedContent" />
    </div>
  </div>
</template>
