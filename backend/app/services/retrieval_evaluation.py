from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
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


Retriever = Callable[[str, int], RetrievalResult]


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
            raise EvaluationDatasetError(f"Invalid evaluation case at line {line_number}: duplicate id `{case.id}`.")
        seen_ids.add(case.id)
        cases.append(case)

    if not cases:
        raise EvaluationDatasetError("Evaluation dataset is empty.")
    return cases


def evaluate_retrieval(cases: list[EvaluationCase], retrieve: Retriever, top_k: int = 5) -> dict[str, Any]:
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

        if case.answerable:
            if not error:
                answerable_scores.append(top_score)
            if rank is not None:
                answerable_hits += 1
                reciprocal_rank_total += 1.0 / rank
        elif not error:
            unanswerable_scores.append(top_score)

        case_reports.append(
            {
                "id": case.id,
                "question": case.question,
                "answerable": case.answerable,
                "hit": rank is not None,
                "first_relevant_rank": rank,
                "top_score": round(top_score, 6),
                "result_chunk_ids": [hit.chunk_id for hit in hits],
                "result_scores": [round(hit.score, 6) for hit in hits],
                "error": error,
            }
        )

    answerable_count = sum(1 for case in cases if case.answerable)
    unanswerable_count = len(cases) - answerable_count
    return {
        "top_k": top_k,
        "total_cases": len(cases),
        "answerable_cases": answerable_count,
        "unanswerable_cases": unanswerable_count,
        "recall_at_k": round(answerable_hits / answerable_count, 6) if answerable_count else 0.0,
        "mrr": round(reciprocal_rank_total / answerable_count, 6) if answerable_count else 0.0,
        "recommended_min_score": _recommend_threshold(answerable_scores, unanswerable_scores),
        "answerable_top_scores": [round(score, 6) for score in answerable_scores],
        "unanswerable_top_scores": [round(score, 6) for score in unanswerable_scores],
        "errors": errors,
        "cases": case_reports,
    }


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
    if answerable and not source_paths and not heading_keywords:
        raise ValueError("answerable case requires expected_source_paths or expected_heading_keywords")

    return EvaluationCase(
        id=case_id,
        question=question,
        answerable=answerable,
        expected_source_paths=source_paths,
        expected_heading_keywords=heading_keywords,
    )


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    values = tuple(str(item).strip() for item in value if str(item).strip())
    if len(values) != len(value):
        raise ValueError(f"{field_name} cannot contain blank values")
    return values


def _first_relevant_rank(case: EvaluationCase, hits: list[RetrievalSearchResult]) -> int | None:
    for rank, hit in enumerate(hits, start=1):
        source_matches = not case.expected_source_paths or hit.source_path in case.expected_source_paths
        searchable_text = f"{' > '.join(hit.heading_path)}\n{hit.content}".lower()
        heading_matches = not case.expected_heading_keywords or any(
            keyword.lower() in searchable_text for keyword in case.expected_heading_keywords
        )
        if source_matches and heading_matches:
            return rank
    return None


def _recommend_threshold(answerable_scores: list[float], unanswerable_scores: list[float]) -> float | None:
    if not answerable_scores or not unanswerable_scores:
        return None

    candidates = sorted({0.0, 1.0, *answerable_scores, *unanswerable_scores})
    best_threshold = 0.0
    best_balanced_accuracy = -1.0
    for threshold in candidates:
        answerable_acceptance = sum(score >= threshold for score in answerable_scores) / len(answerable_scores)
        unanswerable_rejection = sum(score < threshold for score in unanswerable_scores) / len(unanswerable_scores)
        balanced_accuracy = (answerable_acceptance + unanswerable_rejection) / 2
        if balanced_accuracy > best_balanced_accuracy or (
            balanced_accuracy == best_balanced_accuracy and threshold > best_threshold
        ):
            best_balanced_accuracy = balanced_accuracy
            best_threshold = threshold
    return round(best_threshold, 6)
