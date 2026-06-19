export function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export function formatRelativeTime(isoString) {
  if (!isoString) return "—";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  if (diffMs < 0) return "刚刚";
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

export function statusClass(status) {
  if (status === "ready") return "ready";
  if (status === "indexing") return "indexing";
  if (status === "failed") return "failed";
  return "";
}

export function statusLabel(status) {
  return (
    {
      uploaded: "待入库",
      indexing: "入库中",
      ready: "已入库",
      failed: "失败",
    }[status] || "待入库"
  );
}

export function fileExt(filename) {
  return String(filename || "").split(".").pop() || "txt";
}

export function canIndex(file) {
  return ["uploaded", "failed"].includes(file.status);
}
