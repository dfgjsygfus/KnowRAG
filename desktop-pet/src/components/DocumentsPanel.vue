<script setup>
import { computed, onMounted, ref, watch } from "vue";

import ConfirmDialog from "./ConfirmDialog.vue";
import DocumentDetailPanel from "./DocumentDetailPanel.vue";
import { useConfirm } from "../composables/useConfirm.js";
import { useDocuments } from "../composables/useDocuments.js";

const { confirm } = useConfirm();

const {
  documents,
  filteredDocuments,
  isLoading,
  keyword,
  statusFilter,
  selectedIds,
  uploadProgress,
  stats,
  loadDocuments,
  uploadFiles,
  indexDocument,
  indexSelected,
  indexAll,
  deleteDocument,
  deleteSelected,
  toggleSelected,
  setAllSelected,
  formatSize,
  formatRelativeTime,
  statusClass,
  statusLabel,
  fileExt,
  canIndex,
} = useDocuments();

const detailDocument = ref(null);
const fileInput = ref(null);
const dragCounter = ref(0);

const isDragging = computed(() => dragCounter.value > 0);

onMounted(() => {
  void loadDocuments();
});

watch([keyword, statusFilter], () => {
  detailDocument.value = null;
});

function onDragEnter() {
  dragCounter.value += 1;
}

function onDragLeave() {
  dragCounter.value = Math.max(0, dragCounter.value - 1);
}

function onDrop(event) {
  dragCounter.value = 0;
  void uploadFiles(event.dataTransfer.files);
}

function onFileChange(event) {
  void uploadFiles(event.target.files);
  event.target.value = "";
}

function showDetail(doc) {
  detailDocument.value = doc;
}

function closeDetail() {
  detailDocument.value = null;
}

const allFilteredSelected = computed(() => {
  if (filteredDocuments.value.length === 0) return false;
  return filteredDocuments.value.every((doc) => selectedIds.value.has(doc.id));
});

const someFilteredSelected = computed(() => {
  return filteredDocuments.value.some((doc) => selectedIds.value.has(doc.id)) && !allFilteredSelected.value;
});

async function confirmAndDeleteSelected() {
  const ok = await confirm(`确定删除选中的 ${selectedIds.value.size} 个文档吗？此操作不可恢复。`);
  if (!ok) return;
  await deleteSelected();
}

async function confirmAndDeleteDocument(doc) {
  const ok = await confirm(`确定删除 "${doc.filename}" 吗？此操作不可恢复。`);
  if (!ok) return;
  await deleteDocument(doc.id);
  if (detailDocument.value?.id === doc.id) {
    detailDocument.value = null;
  }
}

function resultText(doc) {
  if (doc.status === "ready") return `${doc.stored_count} chunks → Milvus`;
  if (doc.status === "failed") return doc.error_message || "失败";
  return "未入库";
}
</script>

<template>
  <div class="admin-documents">
    <header class="admin-header">
      <div>
        <h1>文档入库</h1>
        <div class="admin-header-meta">{{ stats.total }} 个文件 · {{ stats.stored }} 个已入库</div>
      </div>
      <div style="text-align: right;">
        <button
          class="btn btn-primary"
          :disabled="!documents.some(canIndex)"
          @click="indexAll"
        >
          全部入库
        </button>
      </div>
    </header>

    <div class="admin-body">
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <path d="M14 2v6h6"/>
            </svg>
          </div>
          <div>
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">文件数</div>
          </div>
        </div>
        <div class="stat-card" style="position: relative;">
          <div class="stat-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <path d="M7 10l5 5 5-5"/>
              <path d="M12 15V3"/>
            </svg>
          </div>
          <div>
            <div class="stat-value">{{ stats.stored }}</div>
            <div class="stat-label">已入库</div>
          </div>
          <span
            v-if="stats.failed > 0"
            class="failed-badge"
          >{{ stats.failed }} 失败</span>
        </div>
        <div class="stat-card">
          <div class="stat-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"/>
              <path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>
            </svg>
          </div>
          <div>
            <div class="stat-value">{{ stats.vectors }}</div>
            <div class="stat-label">向量</div>
            <div class="stat-sub">4096 维</div>
          </div>
        </div>
      </div>

      <div class="section-card">
        <div
          :class="['upload-zone', { 'drag-over': isDragging }]"
          @click="fileInput.click()"
          @dragenter.prevent="onDragEnter"
          @dragleave.prevent="onDragLeave"
          @dragover.prevent
          @drop.prevent="onDrop"
        >
          <div v-if="uploadProgress" class="upload-progress">
            <div class="upload-progress-header">
              <span>上传 {{ uploadProgress.current + 1 }}/{{ uploadProgress.total }} · {{ uploadProgress.filename }}</span>
              <span>{{ Math.round((uploadProgress.current / uploadProgress.total) * 100) }}%</span>
            </div>
            <div class="upload-progress-bar-bg">
              <div
                class="upload-progress-bar"
                :style="{ width: `${(uploadProgress.current / uploadProgress.total) * 100}%` }"
              />
            </div>
          </div>
          <template v-else>
            <div class="upload-icon-circle">
              <svg width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                <path d="M17 8l-5-5-5 5"/>
                <path d="M12 3v12"/>
              </svg>
            </div>
            <p>拖拽文件到此处，或 <span class="browse-link">点击浏览</span></p>
            <p class="hint">支持 .md / .markdown / .txt，上传后可预览并写入 Milvus</p>
          </template>
        </div>
        <input
          ref="fileInput"
          type="file"
          accept=".md,.markdown,.txt"
          hidden
          multiple
          @change="onFileChange"
        >

        <div class="toolbar">
          <div class="search-box">
            <span class="search-icon">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#8e8e93" stroke-width="2.2" stroke-linecap="round">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
            </span>
            <input
              v-model="keyword"
              type="text"
              class="search-input"
              placeholder="搜索文件名或路径"
            >
          </div>
          <select
            v-model="statusFilter"
            class="search-input status-select"
          >
            <option value="">全部状态</option>
            <option value="ready">已入库</option>
            <option value="uploaded">待入库</option>
            <option value="indexing">入库中</option>
            <option value="failed">失败</option>
          </select>
          <span class="spacer" />
          <span class="selection-count">已选 {{ selectedIds.size }} 项</span>
          <button
            class="btn btn-primary"
            :disabled="!documents.some((doc) => selectedIds.has(doc.id) && canIndex(doc))"
            @click="indexSelected"
          >
            批量入库
          </button>
          <button
            class="btn btn-danger"
            :disabled="selectedIds.size === 0"
            @click="confirmAndDeleteSelected"
          >
            批量删除
          </button>
        </div>

        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 40px;">
                <input
                  type="checkbox"
                  :checked="allFilteredSelected"
                  :indeterminate.prop="someFilteredSelected"
                  @change="setAllSelected($event.target.checked)"
                >
              </th>
              <th>文件名</th>
              <th style="width: 110px;">状态</th>
              <th style="width: 80px;">大小</th>
              <th style="width: 160px;">入库结果</th>
              <th style="width: 120px;">更新时间</th>
              <th style="width: 140px; text-align: right;">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="isLoading && documents.length === 0">
              <td colspan="7" class="empty-state">
                加载中…
              </td>
            </tr>
            <tr v-else-if="filteredDocuments.length === 0">
              <td colspan="7" class="empty-state">
                <div class="empty-icon-circle">📄</div>
                <h3>还没有文档</h3>
                <p>上传一个 Markdown 文件开始构建知识库。</p>
              </td>
            </tr>
            <tr
              v-for="doc in filteredDocuments"
              :key="doc.id"
            >
              <td style="text-align: center;">
                <input
                  type="checkbox"
                  class="row-checkbox"
                  :checked="selectedIds.has(doc.id)"
                  @change="toggleSelected(doc.id)"
                >
              </td>
              <td>
                <div class="cell-name">
                  <div class="file-icon">
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                      <path d="M14 2v6h6"/>
                    </svg>
                  </div>
                  <span>{{ doc.filename }}</span>
                </div>
              </td>
              <td>
                <span :class="['status-pill', statusClass(doc.status)]">{{ statusLabel(doc.status) }}</span>
              </td>
              <td class="mono">{{ formatSize(doc.size) }}</td>
              <td class="mono">
                <span
                  v-if="doc.status === 'failed'"
                  class="error-detail"
                  :title="doc.error_message"
                >点击查看错误</span>
                <span v-else>{{ resultText(doc) }}</span>
              </td>
              <td style="color: var(--admin-fg-secondary); font-size: 12px;">
                {{ formatRelativeTime(doc.updated_at || doc.created_at) }}
              </td>
              <td style="text-align: right;">
                <div class="cell-actions">
                  <button
                    class="btn btn-sm btn-ghost"
                    @click="showDetail(doc)"
                  >
                    预览
                  </button>
                  <button
                    class="btn btn-sm btn-primary"
                    :disabled="!canIndex(doc)"
                    @click="indexDocument(doc.id)"
                  >
                    入库
                  </button>
                  <button
                    class="btn btn-sm btn-danger"
                    @click="confirmAndDeleteDocument(doc)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <DocumentDetailPanel
          v-if="detailDocument"
          :document="detailDocument"
          @close="closeDetail"
        />
      </div>
    </div>
    <ConfirmDialog />
  </div>
</template>
