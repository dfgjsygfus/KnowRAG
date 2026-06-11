from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from statistics import median, stdev
from typing import Any, Callable

from backend.app.schemas.retrieval import RetrievalResult, RetrievalSearchResult


class EvaluationDatasetError(ValueError):
    """检索评测集格式错误。"""


@dataclass(frozen=True)
class EvaluationCase:
    """一条检索评测问题及其期望命中规则。"""

    id: str
    question: str
    answerable: bool
    expected_source_paths: tuple[str, ...] = ()
    expected_heading_keywords: tuple[str, ...] = ()
    expected_chunk_ids: tuple[str, ...] = ()


Retriever = Callable[[str, int], RetrievalResult]


# ── 加载 ────────────────────────────────────────────────────────────

def load_evaluation_cases(path: str | Path) -> list[EvaluationCase]:
    """从 JSONL 文件加载并校验评测问题。"""

    dataset_path = Path(path)
    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    for line_number, raw_line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            case = _case_from_item(item)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise EvaluationDatasetError(f"Invalid evaluation case at line {line_number}: {exc}") from exc

        if case.id in seen_ids:
            raise EvaluationDatasetError(f"Duplicate id `{case.id}` at line {line_number}.")
        seen_ids.add(case.id)
        cases.append(case)

    if not cases:
        raise EvaluationDatasetError("Evaluation dataset is empty.")
    return cases


# ── 评测 ────────────────────────────────────────────────────────────

def evaluate_retrieval(
    cases: list[EvaluationCase],
    retrieve: Retriever,
    top_k: int = 5,
) -> dict[str, Any]:
    """运行评测集并返回检索指标、逐题结果和推荐阈值。"""

    case_reports: list[dict[str, Any]] = []
    reciprocal_rank_total = 0.0
    answerable_hits = 0
    errors = 0
    answerable_scores: list[float] = []
    unanswerable_scores: list[float] = []

    for case in cases:
        try:
            retrieval = retrieve(case.question, top_k)
            hits = retrieval.results[:top_k]
            top_score = max((hit.score for hit in hits), default=0.0)
            rank = _first_relevant_rank(case, hits) if case.answerable else None
            error = ""
        except Exception as exc:
            hits = []
            top_score = 0.0
            rank = None
            error = str(exc)
            errors += 1

        if case.answerable and not error:
            answerable_scores.append(top_score)
            if rank is not None:
                answerable_hits += 1
                reciprocal_rank_total += 1.0 / rank
        elif not case.answerable and not error:
            unanswerable_scores.append(top_score)

        case_reports.append({
            "id": case.id,
            "question": case.question,
            "answerable": case.answerable,
            "hit": rank is not None,
            "first_relevant_rank": rank,
            "top_score": round(top_score, 6),
            "result_chunk_ids": [hit.chunk_id for hit in hits],
            "result_scores": [round(hit.score, 6) for hit in hits],
            "error": error,
        })

    answerable_count = sum(1 for c in cases if c.answerable)
    unanswerable_count = len(cases) - answerable_count

    return {
        "top_k": top_k,
        "total_cases": len(cases),
        "valid": errors == 0,
        "error_rate": round(errors / len(cases), 6),
        "answerable_cases": answerable_count,
        "unanswerable_cases": unanswerable_count,
        "recall_at_k": round(answerable_hits / answerable_count, 6) if answerable_count else 0.0,
        "mrr": round(reciprocal_rank_total / answerable_count, 6) if answerable_count else 0.0,
        "precision_at_1": _precision_at_k(case_reports, 1),
        "average_rank": _average_rank(case_reports),
        "rank_median": _rank_median(case_reports),
        "rank_stdev": _rank_stdev(case_reports),
        "recommended_min_score": _recommend_threshold(answerable_scores, unanswerable_scores),
        "answerable_top_scores": [round(s, 6) for s in answerable_scores],
        "unanswerable_top_scores": [round(s, 6) for s in unanswerable_scores],
        "errors": errors,
        "cases": case_reports,
        "by_document": _by_document_report(cases, case_reports),
    }


# ── 按文档维度统计 ────────────────────────────────────────────────

def _by_document_report(
    cases: list[EvaluationCase],
    case_reports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按文档分组统计召回率。"""

    doc_cases: dict[str, list[dict[str, Any]]] = {}
    for case, report in zip(cases, case_reports):
        if not case.answerable:
            continue
        key = ", ".join(sorted(case.expected_source_paths)) or "unmapped"
        doc_cases.setdefault(key, []).append(report)

    return [
        {
            "document": doc_path,
            "cases": len(reports),
            "hits": sum(1 for r in reports if r["hit"]),
            "recall": round(sum(1 for r in reports if r["hit"]) / len(reports), 4),
            "avg_first_rank": _average_rank(reports),
        }
        for doc_path, reports in sorted(doc_cases.items())
    ]


# ── 新增指标 ───────────────────────────────────────────────────────

def _precision_at_k(case_reports: list[dict[str, Any]], k: int = 1) -> float:
    """Precision@K: answerable case 中，第 k 个结果是相关的比例。"""
    answerable = [r for r in case_reports if r["first_relevant_rank"] is not None or r["answerable"]]
    hit_at_k = sum(1 for r in answerable if r["first_relevant_rank"] is not None and r["first_relevant_rank"] <= k)
    return round(hit_at_k / len(answerable), 6) if answerable else 0.0


def _average_rank(case_reports: list[dict[str, Any]]) -> float | None:
    ranks = [r["first_relevant_rank"] for r in case_reports if r.get("first_relevant_rank") is not None]
    return round(sum(ranks) / len(ranks), 4) if ranks else None


def _rank_median(case_reports: list[dict[str, Any]]) -> float | None:
    ranks = [r["first_relevant_rank"] for r in case_reports if r.get("first_relevant_rank") is not None]
    return round(median(ranks), 4) if ranks else None


def _rank_stdev(case_reports: list[dict[str, Any]]) -> float | None:
    ranks = [r["first_relevant_rank"] for r in case_reports if r.get("first_relevant_rank") is not None]
    return round(stdev(ranks), 4) if len(ranks) >= 2 else None


# ── 解析 ────────────────────────────────────────────────────────────

def _case_from_item(item: Any) -> EvaluationCase:
    if not isinstance(item, dict):
        raise TypeError("case must be a JSON object")

    case_id = str(item.get("id") or "").strip()
    question = str(item.get("question") or "").strip()
    answerable = item.get("answerable")
    if not case_id:
        raise ValueError("id is required")
    if not question:
        raise ValueError("question is required")
    if not isinstance(answerable, bool):
        raise ValueError("answerable must be true or false")

    source_paths = _string_tuple(item.get("expected_source_paths", []), "expected_source_paths")
    heading_keywords = _string_tuple(item.get("expected_heading_keywords", []), "expected_heading_keywords")
    chunk_ids = _string_tuple(item.get("expected_chunk_ids", []), "expected_chunk_ids")

    if answerable and not source_paths and not heading_keywords and not chunk_ids:
        raise ValueError("answerable case needs expected_source_paths / heading_keywords / chunk_ids")

    return EvaluationCase(
        id=case_id,
        question=question,
        answerable=answerable,
        expected_source_paths=source_paths,
        expected_heading_keywords=heading_keywords,
        expected_chunk_ids=chunk_ids,
    )


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    values = tuple(str(item).strip() for item in value if str(item).strip())
    if len(values) != len(value):
        raise ValueError(f"{field_name} cannot contain blank values")
    return values


# ── 命中判定 ───────────────────────────────────────────────────────

def _first_relevant_rank(case: EvaluationCase, hits: list[RetrievalSearchResult]) -> int | None:
    for rank, hit in enumerate(hits, start=1):
        if _is_relevant(case, hit):
            return rank
    return None


def _is_relevant(case: EvaluationCase, hit: RetrievalSearchResult) -> bool:
    # chunk_id 精配
    if case.expected_chunk_ids and hit.chunk_id in case.expected_chunk_ids:
        return True

    # source_path 匹配
    source_ok = True
    if case.expected_source_paths and hit.source_path not in case.expected_source_paths:
        source_ok = False

    # heading/content keyword 匹配
    keyword_ok = True
    if case.expected_heading_keywords:
        searchable = f"{' > '.join(hit.heading_path)}\n{hit.content}".lower()
        keyword_ok = any(kw.lower() in searchable for kw in case.expected_heading_keywords)

    return source_ok and keyword_ok


# ── 推荐阈值 ───────────────────────────────────────────────────────

def _recommend_threshold(answerable_scores: list[float], unanswerable_scores: list[float]) -> float | None:
    if not answerable_scores or not unanswerable_scores:
        return None

    candidates = sorted({0.0, 1.0, *answerable_scores, *unanswerable_scores})
    best_threshold = 0.0
    best_balanced_accuracy = -1.0
    for threshold in candidates:
        acc = sum(s >= threshold for s in answerable_scores) / len(answerable_scores)
        rej = sum(s < threshold for s in unanswerable_scores) / len(unanswerable_scores)
        ba = (acc + rej) / 2
        if ba > best_balanced_accuracy or (ba == best_balanced_accuracy and threshold > best_threshold):
            best_balanced_accuracy = ba
            best_threshold = threshold
    return round(best_threshold, 6)
