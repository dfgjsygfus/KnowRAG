from __future__ import annotations

import hashlib
from pathlib import Path
import re

from backend.app.schemas.ingestion import (
    ChunkingConfig,
    ChunkingResult,
    CleanedDocument,
    DocumentChunk,
    MarkdownSection,
)


_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]")
_FENCE_RE = re.compile(r"^\s*```")


def chunk_cleaned_document(
    document: CleanedDocument,
    config: ChunkingConfig | None = None,
) -> ChunkingResult:
    """把清洗后的文档切成带元数据的检索 chunk。"""

    config = config or ChunkingConfig()
    chunks: list[DocumentChunk] = []
    pending_sections: list[tuple[int, MarkdownSection]] = []
    pending_tokens = 0

    def flush_pending() -> None:
        nonlocal pending_sections, pending_tokens
        if not pending_sections:
            return

        chunks.append(_build_chunk(document, pending_sections, len(chunks)))
        pending_sections = []
        pending_tokens = 0

    for section_index, section in enumerate(document.sections):
        section_tokens = count_tokens(section.content)

        if section_tokens > config.max_tokens:
            flush_pending()
            chunks.extend(_split_long_section(document, section, section_index, len(chunks), config))
            continue

        can_merge = (
            not pending_sections
            or pending_tokens < config.min_tokens
            or pending_tokens + section_tokens <= config.max_tokens
        )
        if not can_merge:
            flush_pending()

        pending_sections.append((section_index, section))
        pending_tokens += section_tokens

    flush_pending()

    return ChunkingResult(
        source_path=document.source_path,
        document_title=document.title,
        chunks=chunks,
        total_chunks=len(chunks),
    )


def count_tokens(text: str) -> int:
    """粗略估算 token 数，先避免为 MVP 引入 tokenizer 依赖。"""

    return len(_TOKEN_RE.findall(text))


def _build_chunk(
    document: CleanedDocument,
    sections: list[tuple[int, MarkdownSection]],
    chunk_index: int,
) -> DocumentChunk:
    """把一个或多个 section 合并成一个 chunk。"""

    section_indexes = tuple(index for index, _ in sections)
    last_section = sections[-1][1]
    content = "\n\n".join(section.content.strip() for _, section in sections if section.content.strip())

    return DocumentChunk(
        chunk_id=_chunk_id(document.source_path, chunk_index),
        chunk_index=chunk_index,
        source_path=document.source_path,
        document_title=document.title,
        heading=last_section.heading,
        heading_path=last_section.heading_path,
        content=content,
        token_count=count_tokens(content),
        start_line=sections[0][1].start_line,
        end_line=sections[-1][1].end_line,
        section_indexes=section_indexes,
    )


def _split_long_section(
    document: CleanedDocument,
    section: MarkdownSection,
    section_index: int,
    start_chunk_index: int,
    config: ChunkingConfig,
) -> list[DocumentChunk]:
    """把超长 section 按段落和代码块边界切开。"""

    units = _split_section_units(section.content, config.preserve_code_blocks)
    chunks: list[DocumentChunk] = []
    current_units: list[str] = []
    current_tokens = 0

    def flush_current() -> None:
        nonlocal current_units, current_tokens
        if not current_units:
            return

        content = "\n\n".join(unit.strip() for unit in current_units if unit.strip())
        chunk_index = start_chunk_index + len(chunks)
        chunks.append(
            DocumentChunk(
                chunk_id=_chunk_id(document.source_path, chunk_index),
                chunk_index=chunk_index,
                source_path=document.source_path,
                document_title=document.title,
                heading=section.heading,
                heading_path=section.heading_path,
                content=content,
                token_count=count_tokens(content),
                start_line=section.start_line,
                end_line=section.end_line,
                section_indexes=(section_index,),
            )
        )

        current_units = _overlap_units(current_units, config.overlap_tokens)
        current_tokens = count_tokens("\n\n".join(current_units))

    for unit in units:
        unit_tokens = count_tokens(unit)

        if current_units and current_tokens + unit_tokens > config.max_tokens:
            flush_current()

        # 单个代码块或段落超过上限时仍作为整体保留，避免破坏语义边界。
        current_units.append(unit)
        current_tokens += unit_tokens

    flush_current()
    return chunks


def _split_section_units(content: str, preserve_code_blocks: bool) -> list[str]:
    """把 section 拆成可组合单元，代码块会被当作不可切分单元。"""

    if not preserve_code_blocks:
        return [part for part in re.split(r"\n\s*\n", content) if part.strip()]

    units: list[str] = []
    normal_lines: list[str] = []
    code_lines: list[str] = []
    in_fence = False

    def flush_normal() -> None:
        nonlocal normal_lines
        text = "\n".join(normal_lines).strip()
        if text:
            units.extend(part for part in re.split(r"\n\s*\n", text) if part.strip())
        normal_lines = []

    for line in content.split("\n"):
        if _FENCE_RE.match(line):
            if not in_fence:
                flush_normal()
                code_lines = [line]
                in_fence = True
                continue

            code_lines.append(line)
            units.append("\n".join(code_lines).strip())
            code_lines = []
            in_fence = False
            continue

        if in_fence:
            code_lines.append(line)
        else:
            normal_lines.append(line)

    if code_lines:
        units.append("\n".join(code_lines).strip())
    flush_normal()
    return units


def _overlap_units(units: list[str], overlap_tokens: int) -> list[str]:
    """从上一段末尾带少量完整单元作为重叠上下文。"""

    if overlap_tokens <= 0:
        return []

    selected: list[str] = []
    total = 0
    for unit in reversed(units):
        unit_tokens = count_tokens(unit)
        if selected and total + unit_tokens > overlap_tokens:
            break
        selected.append(unit)
        total += unit_tokens
    selected.reverse()
    return selected


def _chunk_id(source_path: str, chunk_index: int) -> str:
    """生成稳定且跨目录不冲突的 chunk 标识。"""

    stem = Path(source_path).stem or "document"
    safe_stem = re.sub(r"\s+", "_", stem)
    normalized_path = str(source_path).replace("\\", "/").strip().lower()
    path_digest = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()[:10]
    return f"{safe_stem}-{path_digest}:{chunk_index:04d}"
