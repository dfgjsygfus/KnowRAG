<script setup>
import { onMounted, ref } from "vue";

import DocumentsPanel from "./DocumentsPanel.vue";
import SettingsPanel from "./SettingsPanel.vue";
import { useToast } from "../composables/useToast.js";

const activeTab = ref("documents");
const { toasts } = useToast();

onMounted(() => {
  import("../assets/admin.css");
});
</script>

<template>
  <div class="admin-view">
    <aside class="admin-sidebar">
      <nav class="admin-nav">
        <div class="admin-nav-label">功能</div>
        <button
          :class="['admin-nav-button', { active: activeTab === 'documents' }]"
          @click="activeTab = 'documents'"
        >
          <span class="admin-nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 19.5A2.5 2.5 0 016.5 17H20"/>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>
              <line x1="8" y1="7" x2="16" y2="7"/>
              <line x1="8" y1="11" x2="16" y2="11"/>
            </svg>
          </span>
          文档入库
        </button>
        <button
          :class="['admin-nav-button', { active: activeTab === 'settings' }]"
          @click="activeTab = 'settings'"
        >
          <span class="admin-nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.7 1.7 0 00.34 1.88l.04.04a2 2 0 01-2.83 2.83l-.04-.04A1.7 1.7 0 0015 19.4a1.7 1.7 0 00-1 .6 1.7 1.7 0 00-.4 1.1V21a2 2 0 01-4 0v-.06a1.7 1.7 0 00-.4-1.1 1.7 1.7 0 00-1-.6 1.7 1.7 0 00-1.88.34l-.04.04a2 2 0 01-2.83-2.83l.04-.04A1.7 1.7 0 004.6 15a1.7 1.7 0 00-.6-1 1.7 1.7 0 00-1.1-.4H3a2 2 0 010-4h.06a1.7 1.7 0 001.1-.4 1.7 1.7 0 00.6-1 1.7 1.7 0 00-.34-1.88l-.04-.04a2 2 0 012.83-2.83l.04.04A1.7 1.7 0 009 4.6a1.7 1.7 0 001-.6 1.7 1.7 0 00.4-1.1V3a2 2 0 014 0v.06a1.7 1.7 0 00.4 1.1 1.7 1.7 0 001 .6 1.7 1.7 0 001.88-.34l.04-.04a2 2 0 012.83 2.83l-.04.04A1.7 1.7 0 0019.4 9c.23.37.57.7 1 .9.33.16.7.24 1.1.24H21a2 2 0 010 4h-.06a1.7 1.7 0 00-1.1.4 1.7 1.7 0 00-.44.46z"/>
            </svg>
          </span>
          模型设置
        </button>
      </nav>
    </aside>

    <main class="admin-main">
      <DocumentsPanel v-if="activeTab === 'documents'" />
      <SettingsPanel v-else />
    </main>

    <div class="toast-container">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast"
      >
        {{ toast.message }}
      </div>
    </div>
  </div>
</template>
