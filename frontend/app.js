const API_BASE_URL = localStorage.getItem("knowrag-api-base") || window.location.origin;

const files = [];
let selectedIndex = -1;
let chatSettings = null;

const uploadZone = document.getElementById("upload-zone");
const fileInput = document.getElementById("file-input");
const fileTableBody = document.getElementById("file-table-body");
const emptyState = document.getElementById("empty-state");
const fileSearch = document.getElementById("file-search");
const detailArea = document.getElementById("detail-area");
const navDocuments = document.getElementById("nav-documents");
const navMilvus = document.getElementById("nav-milvus");
const navSettings = document.getElementById("nav-settings");
const documentSection = document.querySelector(".main-body > .section-card");
const statsRow = document.querySelector(".stats-row");
const headerTitle = document.querySelector(".main-header h1");
const indexAllButton = document.getElementById("btn-index-all");

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
navDocuments.addEventListener("click", showDocumentsView);
navMilvus.addEventListener("click", showMilvusView);
navSettings.addEventListener("click", showSettingsView);

document.getElementById("btn-clear").addEventListener("click", () => {
  clearDocuments();
});
document.getElementById("btn-index-all").addEventListener("click", async () => {
  for (let index = 0; index < files.length; index++) {
    if (!canIndex(files[index])) continue;
    await indexFile(index);
  }
});

fileTableBody.addEventListener("click", event => {
  const preview = event.target.closest("[data-preview]");
  const indexButton = event.target.closest("[data-index]");
  const remove = event.target.closest("[data-remove]");

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
  }
});

function handleFiles(fileList) {
  Array.from(fileList).forEach(file => {
    const ext = fileExt(file.name).toLowerCase();
    if (!["md", "markdown", "txt"].includes(ext)) {
      showToast("仅支持 .md / .markdown / .txt 文件");
      return;
    }

    const reader = new FileReader();
    reader.onload = async () => {
      try {
        // 上传后立即写入 SQLite，刷新页面时可以从后端重新加载列表。
        const document = await apiFetch("/api/documents/upload", {
          method: "POST",
          body: JSON.stringify({
            filename: file.name,
            source_path: `frontend-upload/${file.name}`,
            content: String(reader.result || ""),
            size: file.size,
          }),
        });
        await loadDocuments();
        showToast(document.deduplicated ? `${file.name} 已存在，未重复上传` : `已上传 ${file.name}`);
      } catch (error) {
        showToast(error.message || "上传失败");
      }
    };
    reader.readAsText(file, "utf-8");
  });
}

async function indexFile(index) {
  const file = files[index];
  if (!file || !canIndex(file)) return;

  file.status = "indexing";
  file.error_message = "";
  renderFiles();
  updateStats();

  try {
    const document = await apiFetch(`/api/documents/${file.id}/index`, { method: "POST" });
    files[index] = normalizeDocument(document, file);
    selectedIndex = index;
    await showDetail(index);
    showToast(`已入库 ${file.filename}`);
  } catch (error) {
    file.status = "failed";
    file.error_message = error.message || "入库失败";
    showToast(file.error_message);
  } finally {
    renderFiles();
    updateStats();
  }
}

function renderFiles() {
  const keyword = fileSearch.value.trim().toLowerCase();
  const filtered = files
    .map((file, index) => ({ file, index }))
    .filter(({ file }) => {
      const haystack = `${file.filename}\n${file.source_path}\n${file.content || ""}`.toLowerCase();
      return !keyword || haystack.includes(keyword);
    });

  emptyState.style.display = files.length ? "none" : "block";
  fileTableBody.innerHTML = "";

  filtered.forEach(({ file, index }) => {
    const resultText = file.status === "ready"
      ? `${file.stored_count}/${file.vectors_count} -> Milvus`
      : file.error_message || "未入库";
    const row = document.createElement("tr");
    row.innerHTML = `
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
      <td class="mono">${escapeHTML(resultText)}</td>
      <td>
        <div class="cell-actions">
          <button class="btn btn-sm btn-ghost" data-preview="${index}">预览</button>
          <button class="btn btn-sm btn-primary" data-index="${index}" ${!canIndex(file) ? "disabled" : ""}>入库</button>
          <button class="btn btn-sm btn-danger" data-remove="${index}">删除</button>
        </div>
      </td>
    `;
    fileTableBody.appendChild(row);
  });

  document.getElementById("file-badge").textContent = files.length;
  document.getElementById("btn-index-all").disabled = !files.some(canIndex);
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
        <span class="detail-meta">${escapeHTML(current.updated_at || current.created_at)} · ${formatSize(current.size)}</span>
      </div>
      ${current.status === "ready" ? resultSummaryHTML(current) : ""}
      <div class="detail-panel">
        <div class="detail-header">
          <span>原文预览</span>
          <span class="detail-meta">${escapeHTML(fileExt(current.filename).toUpperCase())}</span>
        </div>
        <pre>${escapeHTML(current.content || "")}</pre>
      </div>
    </div>
  `;
  detailArea.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function resultSummaryHTML(document) {
  return `
    <div class="result-grid">
      <div class="result-item"><b>${document.sections_count}</b><span>Sections</span></div>
      <div class="result-item"><b>${document.chunks_count}</b><span>Chunks</span></div>
      <div class="result-item"><b>${document.vectors_count}</b><span>Vectors</span></div>
      <div class="result-item"><b>${document.stored_count}</b><span>Stored</span></div>
      <div class="result-item"><b>${(document.chunks || []).length}</b><span>Saved Chunks</span></div>
    </div>
    <div class="detail-panel">
      <div class="detail-header">
        <span>入库详情</span>
        <span class="detail-meta">SQLite + Milvus</span>
      </div>
      <pre>${escapeHTML(JSON.stringify(document, null, 2))}</pre>
    </div>
  `;
}

function showDocumentsView() {
  navDocuments.classList.add("active");
  navMilvus.classList.remove("active");
  navSettings.classList.remove("active");
  statsRow.style.display = "";
  documentSection.style.display = "";
  indexAllButton.style.display = "";
  headerTitle.textContent = "文档入库";
  detailArea.style.display = "none";
  updateStats();
}

function showMilvusView() {
  navMilvus.classList.add("active");
  navDocuments.classList.remove("active");
  navSettings.classList.remove("active");
  statsRow.style.display = "";
  documentSection.style.display = "none";
  indexAllButton.style.display = "none";
  headerTitle.textContent = "Milvus 检索测试";
  document.getElementById("header-meta").textContent = `输入问题，验证 Milvus 是否能召回正确 chunk · API ${API_BASE_URL}`;
  detailArea.style.display = "block";
  detailArea.innerHTML = retrievalPanelHTML();
  document.getElementById("retrieval-submit").addEventListener("click", searchRetrieval);
  document.getElementById("retrieval-query").addEventListener("keydown", event => {
    if (event.key === "Enter") {
      searchRetrieval();
    }
  });
}

function retrievalPanelHTML() {
  return `
    <div class="section-card">
      <div class="section-card-header">
        <h2>检索测试</h2>
        <span class="detail-meta">Qwen/Qwen3-VL-Embedding-8B -> Milvus</span>
      </div>
      <div class="retrieval-form">
        <input class="retrieval-input" id="retrieval-query" placeholder="例如：ChiefArchitect 的 Prompt 设计是什么？">
        <input class="retrieval-input" id="retrieval-top-k" type="number" min="1" max="20" value="5" title="Top K">
        <button class="btn btn-primary" id="retrieval-submit">检索</button>
      </div>
      <div class="retrieval-results" id="retrieval-results">
        <div class="empty-state" style="padding: 42px 24px;">
          <h3>🐾 等待检索</h3>
          <p>输入一个问题，旺财帮你在知识库里找答案。</p>
        </div>
      </div>
    </div>
  `;
}

async function searchRetrieval() {
  const queryInput = document.getElementById("retrieval-query");
  const topKInput = document.getElementById("retrieval-top-k");
  const submitButton = document.getElementById("retrieval-submit");
  const resultsArea = document.getElementById("retrieval-results");
  const query = queryInput.value.trim();
  const topK = Math.max(1, Math.min(20, Number(topKInput.value || 5)));

  if (!query) {
    showToast("请输入检索问题");
    return;
  }

  submitButton.disabled = true;
  resultsArea.innerHTML = `<div class="empty-state" style="padding: 42px 24px;"><h3>🐶 检索中</h3><p>旺财正在向量化问题并查询 Milvus...</p></div>`;
  try {
    const result = await apiFetch("/api/retrieval/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    });
    renderRetrievalResults(result);
  } catch (error) {
    resultsArea.innerHTML = `<div class="empty-state" style="padding: 42px 24px;"><h3>😿 检索失败</h3><p>${escapeHTML(error.message || "请检查 Milvus 和 API 配置")}</p></div>`;
  } finally {
    submitButton.disabled = false;
  }
}

function renderRetrievalResults(result) {
  const resultsArea = document.getElementById("retrieval-results");
  if (!result.results || result.results.length === 0) {
    resultsArea.innerHTML = `<div class="empty-state" style="padding: 42px 24px;"><h3>🐾 没有命中</h3><p>可以换一个问法，或检查文档是否已经入库。</p></div>`;
    return;
  }

  resultsArea.innerHTML = result.results.map((item, index) => `
    <div class="retrieval-result">
      <div class="retrieval-result-head">
        <div>
          <div class="retrieval-result-title">${index + 1}. ${escapeHTML(item.document_title || item.chunk_id)}</div>
          <div class="detail-meta">${escapeHTML((item.heading_path || []).join(" > "))} · ${escapeHTML(item.source_path)} · L${item.start_line}-${item.end_line}</div>
        </div>
        <div class="retrieval-score">score ${Number(item.score || 0).toFixed(4)}</div>
      </div>
      <div class="retrieval-result-body">${escapeHTML(item.content || "")}</div>
    </div>
  `).join("");
}

async function showSettingsView() {
  navSettings.classList.add("active");
  navDocuments.classList.remove("active");
  navMilvus.classList.remove("active");
  statsRow.style.display = "none";
  documentSection.style.display = "none";
  indexAllButton.style.display = "none";
  headerTitle.textContent = "模型设置";
  document.getElementById("header-meta").textContent = "配置桌宠问答使用的对话模型 API";
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
  const latestReady = files.find(file => file.status === "ready");
  document.getElementById("stat-files").textContent = files.length;
  document.getElementById("stat-stored").textContent = stored;
  document.getElementById("stat-chunks").textContent = latestReady ? latestReady.chunks_count : 0;
  document.getElementById("stat-vectors").textContent = latestReady ? latestReady.vectors_count : 0;
  document.getElementById("stored-badge").textContent = stored;
  document.getElementById("header-meta").textContent = `${files.length} 个文件 · ${stored} 个已入库 · API ${API_BASE_URL}`;
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

function escapeHTML(value) {
  const div = document.createElement("div");
  div.textContent = String(value);
  return div.innerHTML;
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
    files.splice(0, files.length, ...body.documents.map(normalizeDocument));
  } catch (error) {
    showToast(error.message || "加载文档失败");
  } finally {
    renderFiles();
    updateStats();
  }
}

async function deleteFile(index) {
  const file = files[index];
  if (!file) return;
  try {
    await apiFetch(`/api/documents/${file.id}`, { method: "DELETE" });
    files.splice(index, 1);
    if (selectedIndex === index) {
      selectedIndex = -1;
      detailArea.style.display = "none";
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

function normalizeDocument(document, previous = {}) {
  return {
    ...previous,
    ...document,
    filename: String(document.filename || previous.filename || ""),
    source_path: String(document.source_path || previous.source_path || ""),
    size: Number(document.size || previous.size || 0),
    status: document.status === "indexing" ? "uploaded" : String(document.status || previous.status || "uploaded"),
    sections_count: Number(document.sections_count || 0),
    chunks_count: Number(document.chunks_count || 0),
    vectors_count: Number(document.vectors_count || 0),
    stored_count: Number(document.stored_count || 0),
    error_message: String(document.error_message || ""),
    content: document.content ?? previous.content ?? "",
    chunks: document.chunks || previous.chunks || [],
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
