from __future__ import annotations

import html
from pathlib import Path
import re

from backend.app.schemas.ingestion import CleanedDocument, MarkdownSection


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*]\((?:<[^>]*>|[^)\n]*)\)")
_HTML_IMAGE_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_SPAN_TAG_RE = re.compile(r"</?span\b[^>]*>", re.IGNORECASE)
_STYLE_ATTR_RE = re.compile(r"\s+style=(\"[^\"]*\"|'[^']*')", re.IGNORECASE)
_MARKDOWN_EDGE_DECORATION_RE = re.compile(r"^[\s`~]+|[\s`~]+$")


def clean_markdown_document(markdown: str, source_path: str | Path = "") -> CleanedDocument:
    """清洗 Markdown 文档，并按标题层级拆成结构化 section。"""

    cleaned_text = clean_markdown_text(markdown)
    sections = extract_markdown_sections(cleaned_text)
    title = _document_title(sections, source_path)

    return CleanedDocument(
        source_path=str(source_path),
        title=title,
        cleaned_text=cleaned_text,
        sections=sections,
    )


def clean_markdown_text(markdown: str) -> str:
    """移除非语义 Markdown/HTML 噪声，同时保留原文含义。"""

    text = markdown.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    text = html.unescape(text)

    cleaned_lines: list[str] = []
    in_fence = False

    for line in text.split("\n"):
        stripped = line.strip()

        # 技术文档里的代码块本身是知识内容，因此不要清洗代码块内部文本。
        if stripped.startswith("```"):
            in_fence = not in_fence
            cleaned_lines.append(line.rstrip())
            continue

        if in_fence:
            cleaned_lines.append(line.rstrip())
            continue

        line = _remove_nonsemantic_markup(line)
        if line.strip():
            cleaned_lines.append(line.rstrip())
        elif cleaned_lines and cleaned_lines[-1] != "":
            cleaned_lines.append("")

    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()

    return "\n".join(cleaned_lines)


def extract_markdown_sections(cleaned_text: str) -> list[MarkdownSection]:
    """提取 section，并保留每个 section 的完整标题路径。"""

    lines = cleaned_text.split("\n")
    sections: list[MarkdownSection] = []
    heading_stack: list[str] = []
    current: dict[str, object] | None = None
    current_lines: list[str] = []
    in_fence = False

    def flush(end_line: int) -> None:
        """进入下一个标题前，先落盘当前缓冲区里的 section。"""

        nonlocal current_lines, current
        if current is None:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append(
                    MarkdownSection(
                        heading="",
                        heading_path=(),
                        level=0,
                        content=content,
                        start_line=1,
                        end_line=end_line,
                    )
                )
            current_lines = []
            return

        content = "\n".join(current_lines).strip()
        if content:
            sections.append(
                MarkdownSection(
                    heading=str(current["heading"]),
                    heading_path=tuple(current["heading_path"]),
                    level=int(current["level"]),
                    content=content,
                    start_line=int(current["start_line"]),
                    end_line=end_line,
                )
            )
        current_lines = []

    for index, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            current_lines.append(line)
            continue

        heading_match = None if in_fence else _HEADING_RE.match(line)
        if heading_match:
            flush(index - 1)
            level = len(heading_match.group(1))
            heading = _plain_heading_text(heading_match.group(2))

            # 只保留当前标题上级的祖先标题，再追加当前标题。
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading)
            current = {
                "heading": heading,
                "heading_path": tuple(heading_stack),
                "level": level,
                "start_line": index,
            }
            current_lines = [line]
            continue

        current_lines.append(line)

    flush(len(lines))
    return sections


def _remove_nonsemantic_markup(line: str) -> str:
    """移除会干扰检索质量的纯视觉标记。"""

    line = _MARKDOWN_IMAGE_RE.sub("", line)
    line = _HTML_IMAGE_RE.sub("", line)
    line = _SPAN_TAG_RE.sub("", line)
    line = _STYLE_ATTR_RE.sub("", line)
    return line


def _plain_heading_text(text: str) -> str:
    """归一化标题文本，用于文档标题和元数据路径。"""

    text = _SPAN_TAG_RE.sub("", html.unescape(text))
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace(r"\_", "_")
    text = text.replace("**", "").replace("__", "")
    text = text.replace("~~", "").replace("`", "")
    text = _MARKDOWN_EDGE_DECORATION_RE.sub("", text)
    return text.strip()


def _document_title(sections: list[MarkdownSection], source_path: str | Path) -> str:
    """优先使用第一个标题作为文档标题，没有标题时回退到文件名。"""

    for section in sections:
        if section.heading:
            return section.heading
    if source_path:
        return Path(source_path).stem
    return ""
