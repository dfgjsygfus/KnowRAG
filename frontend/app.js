const API_BASE_URL = localStorage.getItem("knowrag-api-base") || window.location.origin;

const files = [];
let selectedIndex = -1;
let chatSettings = null;

const uploadZone = document.getElementById("upload-zone");
const uploadIcon = document.getElementById("upload-icon");
const uploadPrompt = document.getElementById("upload-prompt");
const uploadProgress = document.getElementById("upload-progress");
const uploadProgressText = document.getElementById("upload-progress-text");
const uploadProgressPercent = document.getElementById("upload-progress-percent");
const uploadProgressBar = document.getElementById("upload-progress-bar");
const fileInput = document.getElementById("file-input");
const fileTableBody = document.getElementById("file-table-body");
const emptyState = document.getElementById("empty-state");
const fileSearch = document.getElementById("file-search");
const statusFilter = document.getElementById("status-filter");
const detailArea = document.getElementById("detail-area");
const navDocuments = document.getElementById("nav-documents");
const navSettings = document.getElementById("nav-settings");
const documentSection = document.querySelector(".main-body > .section-card");
const statsRow = document.querySelector(".stats-row");
const headerTitle = document.querySelector(".main-header h1");
const headerMeta = document.getElementById("header-meta");
const apiStatus = document.getElementById("api-status");
const indexAllButton = document.getElementById("btn-index-all");
const selectAllHeaderCheckbox = document.getElementById("select-all-header");
const bulkIndexButton = document.getElementById("btn-bulk-index");
const bulkDeleteButton = document.getElementById("btn-bulk-delete");
const bulkSelectionCount = document.getElementById("bulk-selection-count");

uploadZone.addEventListener("click", () => fileInput.click());
uploadZone.addEventListener("dragover", event => {
  event.preventDefault();
  uploadZone.classList.add("drag-over");
});
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("drag-over"));
uploadZone.addEventListener("drop", event => {
  event.preventDefault();
  uploadZone.classList.remove("drag-over");
  handleFiles(event.dataTransfer.files);
});
fileInput.addEventListener("change", event => {
  handleFiles(event.target.files);
  fileInput.value = "";
});
fileSearch.addEventListener("input", renderFiles);
statusFilter.addEventListener("change", renderFiles);
navDocuments.addEventListener("click", showDocumentsView);
navSettings.addEventListener("click", showSettingsView);

selectAllHeaderCheckbox.addEventListener("change", () => setAllSelected(selectAllHeaderCheckbox.checked));
bulkIndexButton.addEventListener("click", bulkIndexSelected);
bulkDeleteButton.addEventListener("click", bulkDeleteSelected);

document.getElementById("btn-clear").addEventListener("click", async () => {
  if (!(await confirmDialog("确定删除所有文档及其向量数据吗？此操作不可恢复。"))) return;
  clearDocuments();
});
document.getElementById("btn-index-all").addEventListener("click", async () => {
  for (let index = 0; index < files.length; index++) {
    if (!canIndex(files[index])) continue;
    await indexFile(index, { skipDetail: true });
  }
});

fileTableBody.addEventListener("click", event => {
  const checkbox = event.target.closest("[data-select]");
  const preview = event.target.closest("[data-preview]");
  const indexButton = event.target.closest("[data-index]");
  const remove = event.target.closest("[data-remove]");
  const actionToggle = event.target.closest("[data-action-toggle]");
  const errorDetail = event.target.closest("[data-error]");

  if (checkbox) {
    const index = Number(checkbox.dataset.select);
    toggleSelected(index);
    return;
  }
  if (preview) {
    showDetail(Number(preview.dataset.preview));
    return;
  }
  if (indexButton) {
    indexFile(Number(indexButton.dataset.index));
    return;
  }
  if (remove) {
    deleteFile(Number(remove.dataset.remove));
    return;
  }
  if (actionToggle) {
    toggleActionMenu(actionToggle);
    return;
  }
  if (errorDetail) {
    const index = Number(errorDetail.dataset.error);
    showToast(files[index]?.error_message || "无错误信息");
  }
});

document.addEventListener("click", event => {
  if (!event.target.closest(".action-menu")) {
    closeAllActionMenus();
  }
});

async function handleFiles(fileList) {
  const validFiles = Array.from(fileList).filter(file => {
    const ext = fileExt(file.name).toLowerCase();
    if (["md", "markdown", "txt"].includes(ext)) return true;
    showToast(`不支持的文件类型：${file.name}`);
    return false;
  });

  if (validFiles.length === 0) return;

  setUploadProgressVisible(true);
  let completed = 0;

  for (const file of validFiles) {
    updateUploadProgress(completed, validFiles.length, file.name);
    await uploadSingleFile(file);
    completed += 1;
  }

  updateUploadProgress(completed, validFiles.length, "");
  setTimeout(() => setUploadProgressVisible(false), 800);
  await loadDocuments();
}

async function uploadSingleFile(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const doc = await apiFetch("/api/documents/upload", {
          method: "POST",
          body: JSON.stringify({
            filename: file.name,
            source_path: `frontend-upload/${file.name}`,
            content: String(reader.result || ""),
            size: file.size,
          }),
        });
        showToast(doc.deduplicated ? `${file.name} 已存在，未重复上传` : `已上传 ${file.name}`);
      } catch (error) {
        showToast(`${file.name} 上传失败：${error.message || "未知错误"}`);
      }
      resolve();
    };
    reader.onerror = () => {
      showToast(`${file.name} 读取失败`);
      resolve();
    };
    reader.readAsText(file, "utf-8");
  });
}

function setUploadProgressVisible(visible) {
  uploadIcon.style.display = visible ? "none" : "";
  uploadPrompt.style.display = visible ? "none" : "";
  uploadProgress.style.display = visible ? "block" : "none";
}

function updateUploadProgress(completed, total, filename) {
  const percent = total === 0 ? 0 : Math.round((completed / total) * 100);
  uploadProgressText.textContent = filename
    ? `上传 ${completed + 1}/${total} · ${filename}`
    : `上传完成 ${total} 个文件`;
  uploadProgressPercent.textContent = `${percent}%`;
  uploadProgressBar.style.width = `${percent}%`;
}

async function indexFile(index, options = {}) {
  const { skipDetail = false } = options;
  const file = files[index];
  if (!file || !canIndex(file)) return;

  files[index] = { ...file, status: "indexing", error_message: "" };
  renderFiles();
  updateStats();

  try {
    const doc = await apiFetch(`/api/documents/${file.id}/index`, { method: "POST" });
    files[index] = normalizeDocument(doc, file);
    selectedIndex = index;
    if (!skipDetail) {
      await showDetail(index);
    }
    showToast(`已入库 ${file.filename}`);
  } catch (error) {
    files[index] = { ...files[index], status: "failed", error_message: error.message || "入库失败" };
    showToast(files[index].error_message);
  } finally {
    renderFiles();
    updateStats();
  }
}

function renderFiles() {
  const keyword = fileSearch.value.trim().toLowerCase();
  const statusValue = statusFilter.value;
  const filtered = files
    .map((file, index) => ({ file, index }))
    .filter(({ file }) => {
      const haystack = `${file.filename}\n${file.source_path}\n${file.content || ""}`.toLowerCase();
      const matchesKeyword = !keyword || haystack.includes(keyword);
      const matchesStatus = !statusValue || file.status === statusValue;
      return matchesKeyword && matchesStatus;
    });

  emptyState.style.display = files.length ? "none" : "block";
  fileTableBody.innerHTML = "";

  filtered.forEach(({ file, index }) => {
    const resultText = file.status === "ready"
      ? `${file.stored_count} chunks → Milvus`
      : file.error_message || "未入库";
    const resultCell = file.status === "failed"
      ? `<span class="error-detail" data-error="${index}">点击查看错误</span>`
      : escapeHTML(resultText);
    const row = document.createElement("tr");
    row.innerHTML = `
      <td style="text-align:center;"><input type="checkbox" class="row-checkbox" data-select="${index}" ${file.selected ? "checked" : ""}></td>
      <td>
        <div class="cell-name">
          <div class="file-icon">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/></svg>
          </div>
          <span>${escapeHTML(file.filename)}</span>
        </div>
      </td>
      <td><span class="status-pill ${statusClass(file.status)}">${statusLabel(file.status)}</span></td>
      <td class="mono">${formatSize(file.size)}</td>
      <td class="mono">${resultCell}</td>
      <td style="color: var(--fg-secondary); font-size: 12px;">${formatRelativeTime(file.updated_at || file.created_at)}</td>
      <td style="text-align:right;">
        <div class="cell-actions">
          <button class="btn btn-sm btn-ghost" data-preview="${index}">预览</button>
          <div class="action-menu">
            <button class="action-menu-button" data-action-toggle="${index}">⋯</button>
            <div class="action-menu-list">
              <button class="action-menu-item" data-index="${index}" ${!canIndex(file) ? "disabled" : ""}>入库</button>
              <button class="action-menu-item danger" data-remove="${index}">删除</button>
            </div>
          </div>
        </div>
      </td>
    `;
    fileTableBody.appendChild(row);
  });

  updateSelectionUI();
  document.getElementById("file-badge").textContent = files.length;
  document.getElementById("btn-index-all").disabled = !files.some(canIndex);
}

function updateSelectionUI() {
  const selectedCount = files.filter(file => file.selected).length;
  const filteredCount = files.filter(file => matchesFilters(file)).length;
  const allFilteredSelected = filteredCount > 0 && files.filter(file => matchesFilters(file)).every(file => file.selected);

  selectAllHeaderCheckbox.checked = allFilteredSelected;
  selectAllHeaderCheckbox.indeterminate = selectedCount > 0 && !allFilteredSelected;
  bulkSelectionCount.textContent = `已选 ${selectedCount} 项`;
  bulkIndexButton.disabled = !files.some(file => file.selected && canIndex(file));
  bulkDeleteButton.disabled = selectedCount === 0;
}

function matchesFilters(file) {
  const keyword = fileSearch.value.trim().toLowerCase();
  const statusValue = statusFilter.value;
  const haystack = `${file.filename}\n${file.source_path}\n${file.content || ""}`.toLowerCase();
  const matchesKeyword = !keyword || haystack.includes(keyword);
  const matchesStatus = !statusValue || file.status === statusValue;
  return matchesKeyword && matchesStatus;
}

function toggleSelected(index) {
  const file = files[index];
  if (!file) return;
  files[index] = { ...file, selected: !file.selected };
  renderFiles();
}

function setAllSelected(selected) {
  files.forEach((file, index) => {
    if (matchesFilters(file)) {
      files[index] = { ...file, selected };
    }
  });
  renderFiles();
}

async function bulkIndexSelected() {
  const indices = files
    .map((file, index) => ({ file, index }))
    .filter(({ file }) => file.selected && canIndex(file))
    .map(({ index }) => index);

  for (const index of indices) {
    await indexFile(index, { skipDetail: true });
  }
}

async function bulkDeleteSelected() {
  const indices = files
    .map((file, index) => ({ file, index }))
    .filter(({ file }) => file.selected)
    .map(({ index }) => index)
    .sort((a, b) => b - a);

  if (indices.length === 0) return;
  if (!(await confirmDialog(`确定删除选中的 ${indices.length} 个文档吗？此操作不可恢复。`))) return;

  for (const index of indices) {
    await deleteFileAtIndex(index);
  }
}

function toggleActionMenu(button) {
  const menu = button.parentElement;
  const isOpen = menu.classList.contains("open");
  closeAllActionMenus();
  if (!isOpen) {
    menu.classList.add("open");
  }
}

function closeAllActionMenus() {
  document.querySelectorAll(".action-menu.open").forEach(menu => menu.classList.remove("open"));
}

async function confirmDialog(message) {
  return window.confirm(message);
}

async function showDetail(index) {
  const file = files[index];
  if (!file) return;
  selectedIndex = index;

  if (!file.content) {
    try {
      // 列表只拿摘要，点预览时再拉正文，避免首页加载太重。
      const detail = await apiFetch(`/api/documents/${file.id}`);
      files[index] = normalizeDocument(detail, file);
    } catch (error) {
      showToast(error.message || "读取详情失败");
      return;
    }
  }

  const current = files[index];
  detailArea.style.display = "block";
  detailArea.innerHTML = `
    <div class="section-card">
      <div class="section-card-header">
        <h2>${escapeHTML(current.filename)}</h2>
        <div style="display:flex;align-items:center;gap:12px;">
          <span class="detail-meta">${escapeHTML(current.updated_at || current.created_at)} · ${formatSize(current.size)}</span>
          <button class="detail-close" id="detail-close" title="关闭预览">✕</button>
        </div>
      </div>
      ${current.status === "ready" ? resultSummaryHTML(current) : ""}
      <div class="detail-panel">
        <div class="detail-header">
          <span>原文预览</span>
          <span class="detail-meta">${escapeHTML(fileExt(current.filename).toUpperCase())}</span>
        </div>
        <div class="markdown-body">${renderMarkdown(current.content)}</div>
      </div>
    </div>
  `;
  document.getElementById("detail-close").addEventListener("click", closeDetail);
  detailArea.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function closeDetail() {
  detailArea.style.display = "none";
  selectedIndex = -1;
}

function resultSummaryHTML(doc) {
  return `
    <div class="result-grid">
      <div class="result-item"><b>${doc.sections_count}</b><span>Sections</span></div>
      <div class="result-item"><b>${doc.chunks_count}</b><span>Chunks</span></div>
      <div class="result-item"><b>${doc.vectors_count}</b><span>Vectors</span></div>
      <div class="result-item"><b>${doc.stored_count}</b><span>Stored</span></div>
      <div class="result-item"><b>${(doc.chunks || []).length}</b><span>Saved Chunks</span></div>
    </div>`;
}

function showDocumentsView() {
  navDocuments.classList.add("active");
  navSettings.classList.remove("active");
  statsRow.style.display = "";
  documentSection.style.display = "";
  indexAllButton.parentElement.style.display = "";
  headerTitle.textContent = "文档入库";
  detailArea.style.display = "none";
  updateStats();
}

async function showSettingsView() {
  navSettings.classList.add("active");
  navDocuments.classList.remove("active");
  statsRow.style.display = "none";
  documentSection.style.display = "none";
  indexAllButton.parentElement.style.display = "none";
  headerTitle.textContent = "模型设置";
  headerMeta.textContent = "配置对话模型 API";
  apiStatus.textContent = `API: ${API_BASE_URL.replace(/^https?:\/\//, "")} ✓`;
  apiStatus.className = "api-status-ok";
  detailArea.style.display = "block";
  detailArea.innerHTML = settingsPanelHTML();
  bindSettingsForm();
  await loadChatModelSettings();
}

function settingsPanelHTML() {
  return `
    <div class="section-card">
      <div class="section-card-header">
        <h2>对话模型</h2>
        <span class="detail-meta">OpenAI-compatible Chat Completions</span>
      </div>
      <form class="settings-form" id="chat-model-form">
        <div class="settings-field">
          <label for="chat-model-provider">接入厂商</label>
          <select class="retrieval-input" id="chat-model-provider">
            <option value="deepseek">DeepSeek</option>
            <option value="qwen">Qwen</option>
            <option value="custom">自定义</option>
          </select>
        </div>
        <div class="settings-field">
          <label for="chat-model-timeout">超时时间（秒）</label>
          <input class="retrieval-input" id="chat-model-timeout" type="number" min="5" max="600" value="120">
        </div>
        <div class="settings-field full">
          <label for="chat-model-api-key">API Key</label>
          <input class="retrieval-input" id="chat-model-api-key" type="password" autocomplete="off" placeholder="输入新的 API Key">
        </div>
        <div class="settings-field full">
          <label for="chat-model-base-url">Base URL</label>
          <input class="retrieval-input" id="chat-model-base-url" autocomplete="off">
        </div>
        <div class="settings-field full">
          <label for="chat-model-name">模型名</label>
          <input class="retrieval-input" id="chat-model-name" autocomplete="off">
        </div>
        <div class="settings-actions">
          <span class="settings-note" id="chat-model-key-state">正在读取配置...</span>
          <button class="btn btn-ghost" id="chat-model-test" type="button">测试连接</button>
          <button class="btn btn-primary" id="chat-model-save" type="submit">保存设置</button>
        </div>
      </form>
    </div>
  `;
}

function bindSettingsForm() {
  const providerInput = document.getElementById("chat-model-provider");
  const form = document.getElementById("chat-model-form");
  const testButton = document.getElementById("chat-model-test");
  providerInput.addEventListener("change", () => applyChatProviderPreset(providerInput.value));
  testButton.addEventListener("click", testChatModelConnection);
  form.addEventListener("submit", saveChatModelSettings);
}

async function loadChatModelSettings() {
  try {
    const result = await apiFetch("/api/settings/chat-model");
    chatSettings = result;
    renderChatModelSettings(result);
  } catch (error) {
    document.getElementById("chat-model-key-state").textContent = error.message || "读取配置失败";
  }
}

function renderChatModelSettings(settings) {
  const provider = settings.provider || "qwen";
  const profile = settings.profiles?.[provider] || settings;
  document.getElementById("chat-model-provider").value = provider;
  document.getElementById("chat-model-api-key").value = "";
  document.getElementById("chat-model-base-url").value = profile.base_url || "";
  document.getElementById("chat-model-name").value = profile.model || "";
  document.getElementById("chat-model-timeout").value = profile.timeout_seconds || 120;
  renderChatProfileKeyState(profile);
}

function renderChatProfileKeyState(profile) {
  const apiKeyInput = document.getElementById("chat-model-api-key");
  apiKeyInput.placeholder = profile?.api_key_set
    ? "已保存，留空则不修改"
    : "输入 API Key";
  document.getElementById("chat-model-key-state").textContent = profile?.api_key_set
    ? "API Key 已保存"
    : "尚未保存 API Key";
}

function applyChatProviderPreset(provider) {
  const profile = chatSettings?.profiles?.[provider];
  const preset = chatSettings?.presets?.[provider];
  if (!preset) return;
  document.getElementById("chat-model-api-key").value = "";
  document.getElementById("chat-model-base-url").value = profile?.base_url ?? preset.base_url;
  document.getElementById("chat-model-name").value = profile?.model ?? preset.model;
  document.getElementById("chat-model-timeout").value = profile?.timeout_seconds || 120;
  renderChatProfileKeyState(profile || { api_key_set: false });
}

async function saveChatModelSettings(event) {
  event.preventDefault();
  const saveButton = document.getElementById("chat-model-save");
  saveButton.disabled = true;
  try {
    const result = await apiFetch("/api/settings/chat-model", {
      method: "PUT",
      body: JSON.stringify(chatModelSettingsPayload()),
    });
    chatSettings = result;
    renderChatModelSettings(result);
    showToast("模型设置已保存");
  } catch (error) {
    showToast(error.message || "保存模型设置失败");
  } finally {
    saveButton.disabled = false;
  }
}

async function testChatModelConnection() {
  const testButton = document.getElementById("chat-model-test");
  const keyState = document.getElementById("chat-model-key-state");
  testButton.disabled = true;
  keyState.textContent = "正在测试连接...";
  try {
    const result = await apiFetch("/api/settings/chat-model/test", {
      method: "POST",
      body: JSON.stringify(chatModelSettingsPayload()),
    });
    if (result.ok) {
      keyState.textContent = `连接成功：${result.model}`;
      showToast("模型连接测试成功");
    } else {
      keyState.textContent = result.message || "连接失败，请检查配置";
      showToast(result.message || "模型连接测试失败");
    }
  } catch (error) {
    keyState.textContent = error.message || "连接测试失败";
    showToast(error.message || "连接测试失败");
  } finally {
    testButton.disabled = false;
  }
}

function chatModelSettingsPayload() {
  return {
    provider: document.getElementById("chat-model-provider").value,
    api_key: document.getElementById("chat-model-api-key").value,
    base_url: document.getElementById("chat-model-base-url").value,
    model: document.getElementById("chat-model-name").value,
    timeout_seconds: Number(document.getElementById("chat-model-timeout").value || 120),
  };
}

function updateStats() {
  const stored = files.filter(file => file.status === "ready").length;
  const failed = files.filter(file => file.status === "failed").length;
  const latestReady = files
    .filter(file => file.status === "ready")
    .sort((a, b) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime())[0];
  document.getElementById("stat-files").textContent = files.length;
  document.getElementById("stat-stored").textContent = stored;
  document.getElementById("stat-vectors").textContent = latestReady ? latestReady.vectors_count : 0;
  headerMeta.textContent = `${files.length} 个文件 · ${stored} 个已入库`;

  const failedBadge = document.getElementById("stat-failed-badge");
  if (failedBadge) {
    failedBadge.textContent = `${failed} 失败`;
    failedBadge.style.display = failed > 0 ? "block" : "none";
  }
}

function renderApiStatus(isError = false) {
  apiStatus.textContent = `API: ${API_BASE_URL.replace(/^https?:\/\//, "")} ${isError ? "✗" : "✓"}`;
  apiStatus.className = isError ? "api-status-error" : "api-status-ok";
}

function setApiStatusFromResponse(ok) {
  renderApiStatus(!ok);
}

function statusClass(status) {
  return status === "ready" ? "ready" : status === "indexing" ? "indexing" : status === "failed" ? "failed" : "";
}

function statusLabel(status) {
  return {
    uploaded: "待入库",
    indexing: "入库中",
    ready: "已入库",
    failed: "失败",
  }[status] || "待入库";
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function formatRelativeTime(isoString) {
  if (!isoString) return "—";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  if (diffHour < 24) return `${diffHour} 小时前`;
  if (diffDay < 7) return `${diffDay} 天前`;
  return date.toLocaleDateString("zh-CN");
}

function escapeHTML(value) {
  const div = document.createElement("div");
  div.textContent = String(value);
  return div.innerHTML;
}

function renderMarkdown(markdown) {
  if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
    return `<pre>${escapeHTML(markdown || "")}</pre>`;
  }
  try {
    const rawHtml = marked.parse(String(markdown || ""));
    return DOMPurify.sanitize(rawHtml);
  } catch (error) {
    return `<pre>${escapeHTML(markdown || "")}</pre>`;
  }
}

function showToast(message) {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 2600);
}

async function loadDocuments() {
  try {
    const body = await apiFetch("/api/documents");
    const selectedIds = new Set(files.filter(file => file.selected).map(file => file.id));
    files.splice(0, files.length, ...body.documents.map(doc => normalizeDocument(doc, { selected: selectedIds.has(doc.id) })));
    renderApiStatus(false);
  } catch (error) {
    showToast(error.message || "加载文档失败");
    renderApiStatus(true);
  } finally {
    renderFiles();
    updateStats();
  }
}

async function deleteFile(index) {
  const file = files[index];
  if (!file) return;
  if (!(await confirmDialog(`确定删除 "${file.filename}" 吗？此操作不可恢复。`))) return;
  await deleteFileAtIndex(index);
}

async function deleteFileAtIndex(index) {
  const file = files[index];
  if (!file) return;
  try {
    await apiFetch(`/api/documents/${file.id}`, { method: "DELETE" });
    files.splice(index, 1);
    if (selectedIndex === index) {
      selectedIndex = -1;
      detailArea.style.display = "none";
    } else if (selectedIndex > index) {
      selectedIndex -= 1;
    }
    renderFiles();
    updateStats();
  } catch (error) {
    showToast(error.message || "删除失败");
  }
}

async function clearDocuments() {
  try {
    const ids = files.map(file => file.id);
    for (const id of ids) {
      await apiFetch(`/api/documents/${id}`, { method: "DELETE" });
    }
    files.splice(0, files.length);
    selectedIndex = -1;
    detailArea.style.display = "none";
    renderFiles();
    updateStats();
  } catch (error) {
    showToast(error.message || "清空失败");
  }
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return body;
}

function normalizeDocument(doc, previous = {}) {
  return {
    ...previous,
    ...doc,
    selected: previous.selected || false,
    filename: String(doc.filename || previous.filename || ""),
    source_path: String(doc.source_path || previous.source_path || ""),
    size: Number(doc.size || previous.size || 0),
    status: String(doc.status || previous.status || "uploaded"),
    sections_count: Number(doc.sections_count || 0),
    chunks_count: Number(doc.chunks_count || 0),
    vectors_count: Number(doc.vectors_count || 0),
    stored_count: Number(doc.stored_count || 0),
    error_message: String(doc.error_message || ""),
    content: doc.content ?? previous.content ?? "",
    chunks: doc.chunks || previous.chunks || [],
  };
}

function canIndex(file) {
  return ["uploaded", "failed"].includes(file.status);
}

function fileExt(filename) {
  return String(filename || "").split(".").pop() || "txt";
}

renderFiles();
updateStats();
loadDocuments();
