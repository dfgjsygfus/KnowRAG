import { computed, ref } from "vue";

import {
  canIndex,
  fileExt,
  formatRelativeTime,
  formatSize,
  statusClass,
  statusLabel,
} from "../lib/format.js";
import { useAdminApi } from "./useAdminApi.js";
import { useToast } from "./useToast.js";

const VALID_EXTENSIONS = new Set(["md", "markdown", "txt"]);

export function useDocuments() {
  const api = useAdminApi();
  const { showToast } = useToast();

  const documents = ref([]);
  const isLoading = ref(false);
  const keyword = ref("");
  const statusFilter = ref("");
  const selectedIds = ref(new Set());
  const uploadProgress = ref(null);

  const filteredDocuments = computed(() => {
    const lowerKeyword = keyword.value.trim().toLowerCase();
    return documents.value.filter((doc) => {
      const haystack = `${doc.filename}\n${doc.source_path}\n${doc.content || ""}`.toLowerCase();
      const matchesKeyword = !lowerKeyword || haystack.includes(lowerKeyword);
      const matchesStatus = !statusFilter.value || doc.status === statusFilter.value;
      return matchesKeyword && matchesStatus;
    });
  });

  const stats = computed(() => {
    const stored = documents.value.filter((doc) => doc.status === "ready").length;
    const failed = documents.value.filter((doc) => doc.status === "failed").length;
    const latestReady = documents.value
      .filter((doc) => doc.status === "ready")
      .sort(
        (a, b) =>
          new Date(b.updated_at || b.created_at || 0).getTime() -
          new Date(a.updated_at || a.created_at || 0).getTime(),
      )[0];
    return {
      total: documents.value.length,
      stored,
      failed,
      vectors: latestReady ? latestReady.vectors_count : 0,
    };
  });

  async function loadDocuments() {
    isLoading.value = true;
    try {
      const body = await api.fetchDocuments();
      const previousSelected = selectedIds.value;
      documents.value = (body.documents || []).map((doc) => normalizeDocument(doc));
      selectedIds.value = new Set(
        [...previousSelected].filter((id) => documents.value.some((doc) => doc.id === id)),
      );
    } catch (error) {
      showToast(error.message || "加载文档失败");
    } finally {
      isLoading.value = false;
    }
  }

  async function uploadFiles(fileList) {
    const files = Array.from(fileList).filter((file) => {
      const ext = fileExt(file.name).toLowerCase();
      if (VALID_EXTENSIONS.has(ext)) return true;
      showToast(`不支持的文件类型：${file.name}`);
      return false;
    });

    if (files.length === 0) return;

    uploadProgress.value = { current: 0, total: files.length, filename: "" };

    for (let index = 0; index < files.length; index += 1) {
      const file = files[index];
      uploadProgress.value = { ...uploadProgress.value, filename: file.name };
      await uploadSingleFile(file);
      uploadProgress.value = { ...uploadProgress.value, current: index + 1 };
    }

    uploadProgress.value = null;
    await loadDocuments();
  }

  function uploadSingleFile(file) {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const doc = await api.uploadDocument({
            filename: file.name,
            source_path: `frontend-upload/${file.name}`,
            content: String(reader.result || ""),
            size: file.size,
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

  async function indexDocument(documentId) {
    const index = documents.value.findIndex((doc) => doc.id === documentId);
    if (index === -1) return;
    const file = documents.value[index];
    if (!canIndex(file)) return;

    documents.value = documents.value.map((doc, i) =>
      i === index ? { ...doc, status: "indexing", error_message: "" } : doc,
    );

    try {
      const doc = await api.indexDocument(file.id);
      documents.value = documents.value.map((item) =>
        item.id === doc.id ? normalizeDocument(doc, item) : item,
      );
      showToast(`已入库 ${file.filename}`);
    } catch (error) {
      documents.value = documents.value.map((item) =>
        item.id === file.id ? { ...item, status: "failed", error_message: error.message || "入库失败" } : item,
      );
      showToast(error.message || "入库失败");
    }
  }

  async function indexSelected() {
    const ids = [...selectedIds.value];
    for (const id of ids) {
      const doc = documents.value.find((item) => item.id === id);
      if (doc && canIndex(doc)) {
        await indexDocument(id);
      }
    }
  }

  async function indexAll() {
    const ids = documents.value.filter((doc) => canIndex(doc)).map((doc) => doc.id);
    for (const id of ids) {
      await indexDocument(id);
    }
  }

  async function deleteDocument(documentId) {
    const doc = documents.value.find((item) => item.id === documentId);
    if (!doc) return;
    try {
      await api.deleteDocument(documentId);
      documents.value = documents.value.filter((item) => item.id !== documentId);
      selectedIds.value = new Set([...selectedIds.value].filter((id) => id !== documentId));
      showToast(`已删除 ${doc.filename}`);
    } catch (error) {
      showToast(error.message || "删除失败");
    }
  }

  async function deleteSelected() {
    const ids = [...selectedIds.value];
    for (const id of ids) {
      await deleteDocument(id);
    }
  }

  function toggleSelected(documentId) {
    const next = new Set(selectedIds.value);
    if (next.has(documentId)) {
      next.delete(documentId);
    } else {
      next.add(documentId);
    }
    selectedIds.value = next;
  }

  function setAllSelected(selected) {
    const visibleIds = new Set(filteredDocuments.value.map((doc) => doc.id));
    if (selected) {
      selectedIds.value = new Set([...selectedIds.value, ...visibleIds]);
    } else {
      selectedIds.value = new Set([...selectedIds.value].filter((id) => !visibleIds.has(id)));
    }
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

  return {
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
    // Expose format helpers for template use
    formatSize,
    formatRelativeTime,
    statusClass,
    statusLabel,
    fileExt,
    canIndex,
  };
}
