<script setup>
import { onMounted } from "vue";

import { useChatModelSettings } from "../composables/useChatModelSettings.js";

const {
  isLoading,
  isSaving,
  isTesting,
  provider,
  apiKey,
  apiKeySet,
  baseUrl,
  model,
  timeoutSeconds,
  loadSettings,
  applyProviderPreset,
  saveSettings,
  testConnection,
} = useChatModelSettings();

onMounted(() => {
  void loadSettings();
});

function onProviderChange() {
  applyProviderPreset();
}

async function onSubmit(event) {
  event.preventDefault();
  await saveSettings();
}
</script>

<template>
  <div class="admin-settings">
    <header class="admin-header">
      <div>
        <h1>模型设置</h1>
        <div class="admin-header-meta">配置对话模型 API</div>
      </div>
    </header>

    <div class="admin-body">
      <div class="section-card">
        <div class="section-card-header">
          <h2>对话模型</h2>
          <span class="detail-meta">OpenAI-compatible Chat Completions</span>
        </div>

        <form class="settings-form" @submit="onSubmit">
          <div class="settings-field">
            <label for="chat-model-provider">接入厂商</label>
            <select
              id="chat-model-provider"
              v-model="provider"
              class="retrieval-input"
              @change="onProviderChange"
            >
              <option value="deepseek">DeepSeek</option>
              <option value="qwen">Qwen</option>
              <option value="custom">自定义</option>
            </select>
          </div>

          <div class="settings-field">
            <label for="chat-model-timeout">超时时间（秒）</label>
            <input
              id="chat-model-timeout"
              v-model.number="timeoutSeconds"
              type="number"
              min="5"
              max="600"
              class="retrieval-input"
            >
          </div>

          <div class="settings-field full">
            <label for="chat-model-api-key">API Key</label>
            <input
              id="chat-model-api-key"
              v-model="apiKey"
              type="password"
              autocomplete="off"
              class="retrieval-input"
              :placeholder="apiKeySet ? '已保存，留空则不修改' : '输入 API Key'"
            >
          </div>

          <div class="settings-field full">
            <label for="chat-model-base-url">Base URL</label>
            <input
              id="chat-model-base-url"
              v-model="baseUrl"
              autocomplete="off"
              class="retrieval-input"
            >
          </div>

          <div class="settings-field full">
            <label for="chat-model-name">模型名</label>
            <input
              id="chat-model-name"
              v-model="model"
              autocomplete="off"
              class="retrieval-input"
            >
          </div>

          <div class="settings-actions">
            <span class="settings-note">
              {{ isLoading ? "正在读取配置…" : apiKeySet ? "API Key 已保存" : "尚未保存 API Key" }}
            </span>
            <button
              type="button"
              class="btn btn-ghost"
              :disabled="isTesting"
              @click="testConnection"
            >
              {{ isTesting ? "测试中…" : "测试连接" }}
            </button>
            <button
              type="submit"
              class="btn btn-primary"
              :disabled="isSaving"
            >
              {{ isSaving ? "保存中…" : "保存设置" }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
