import DOMPurify from "isomorphic-dompurify";
import { marked } from "marked";

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
  }
});

export function renderMarkdown(markdown) {
  try {
    const rawHtml = marked.parse(String(markdown || ""));
    return DOMPurify.sanitize(rawHtml);
  } catch {
    return escapeHtmlFallback(markdown);
  }
}

export function formatAssistantContent(content) {
  const trimmed = String(content || "").trim();
  if (!/^[[{]/.test(trimmed)) return content;

  try {
    const parsed = JSON.parse(trimmed);
    return `\`\`\`json\n${JSON.stringify(parsed, null, 2)}\n\`\`\``;
  } catch {
    return content;
  }
}

const MAX_EXCERPT_CHARS = 220;

/**
 * Return a short plain-text excerpt from a chunk for citation previews.
 * Strips Markdown formatting, collapses whitespace, and trims to a
 * readable length without breaking in the middle of a sentence.
 */
export function excerptText(markdown, maxLength = MAX_EXCERPT_CHARS) {
  const text = String(markdown || "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[#*_~`>|\-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (text.length <= maxLength) return text;

  const cut = text.slice(0, maxLength + 1);
  const lastSentence = cut.lastIndexOf("。", maxLength);
  const lastPunct = Math.max(lastSentence, cut.lastIndexOf("；", maxLength));
  if (lastPunct > maxLength * 0.4) return text.slice(0, lastPunct + 1);
  return text.slice(0, maxLength).trimEnd() + "…";
}

function escapeHtmlFallback(value) {
  const text = String(value || "");
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
  return `<pre>${escaped}</pre>`;
}
