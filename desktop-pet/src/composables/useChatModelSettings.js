import { computed, ref } from "vue";

import { useAdminApi } from "./useAdminApi.js";
import { useToast } from "./useToast.js";

export function useChatModelSettings() {
  const api = useAdminApi();
  const { showToast } = useToast();

  const settings = ref(null);
  const isLoading = ref(false);
  const isSaving = ref(false);
  const isTesting = ref(false);

  const provider = ref("qwen");
  const apiKey = ref("");
  const baseUrl = ref("");
  const model = ref("");
  const timeoutSeconds = ref(120);

  const apiKeySet = computed(() => {
    const currentProvider = provider.value;
    const profile = settings.value?.profiles?.[currentProvider];
    return Boolean(profile?.api_key_set);
  });
  async function loadSettings() {
    isLoading.value = true;
    try {
      const result = await api.fetchChatModelSettings();
      settings.value = result;
      renderChatModelSettings(result);
    } catch (error) {
      showToast(error.message || "读取配置失败");
    } finally {
      isLoading.value = false;
    }
  }

  function renderChatModelSettings(result) {
    const currentProvider = result.provider || "qwen";
    const profile = result.profiles?.[currentProvider] || result;
    provider.value = currentProvider;
    apiKey.value = "";
    baseUrl.value = profile.base_url || "";
    model.value = profile.model || "";
    timeoutSeconds.value = profile.timeout_seconds || 120;
  }

  function applyProviderPreset() {
    const preset = settings.value?.presets?.[provider.value];
    const profile = settings.value?.profiles?.[provider.value];
    if (!preset) return;
    baseUrl.value = profile?.base_url ?? preset.base_url;
    model.value = profile?.model ?? preset.model;
    timeoutSeconds.value = profile?.timeout_seconds || 120;
    apiKey.value = "";
  }

  async function saveSettings() {
    isSaving.value = true;
    try {
      const result = await api.updateChatModelSettings(buildPayload());
      settings.value = result;
      renderChatModelSettings(result);
      showToast("模型设置已保存");
    } catch (error) {
      showToast(error.message || "保存模型设置失败");
    } finally {
      isSaving.value = false;
    }
  }

  async function testConnection() {
    isTesting.value = true;
    try {
      const result = await api.testChatModelConnection(buildPayload());
      if (result.ok) {
        showToast(`连接成功：${result.model}`);
      } else {
        showToast(result.message || "连接失败，请检查配置");
      }
    } catch (error) {
      showToast(error.message || "连接测试失败");
    } finally {
      isTesting.value = false;
    }
  }

  function buildPayload() {
    return {
      provider: provider.value,
      api_key: apiKey.value,
      base_url: baseUrl.value,
      model: model.value,
      timeout_seconds: Number(timeoutSeconds.value || 120),
    };
  }

  return {
    settings,
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
  };
}
