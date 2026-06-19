from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.schemas.query_routing import QueryIntent
from backend.app.services.openai_chat import OpenAIChatClient
from backend.app.services.rag_service import stream_rag_answer
from backend.app.services.retrieval_evaluation import EvaluationCase, load_evaluation_cases


JUDGE_SYSTEM_PROMPT = (
    "你是一个严格的 RAG 答案质量评估员。请根据「问题」和「检索到的资料」，判断「模型回答」是否正确。\n"
    "评分标准（1-5分）：\n"
    "5 分：完全正确，基于资料完整回答了问题，无编造。\n"
    "4 分：基本正确，但有小遗漏或措辞不够精确。\n"
    "3 分：部分正确，包含有效信息但也有错误或遗漏关键内容。\n"
    "2 分：严重偏离，大量内容错误或答非所问。\n"
    "1 分：完全错误、编造或拒绝回答一个可回答的问题。\n\n"
    "对于「资料里没有足够信息」的问题，如果模型明确说明资料不足、无法回答，则视为正确（5分）。\n"
    "如果模型在资料不足时仍然编造答案，则视为错误（1-2分）。\n\n"
    "请只输出一个 JSON 对象，不要有任何其他文字。JSON 字段：\n"
    "- correct: true/false（4分及以上为 true）\n"
    "- score: 1-5 的整数\n"
    "- reason: 简短说明评分理由（30字以内）"
)


def _build_judge_messages(case: EvaluationCase, answer: str, contexts: list[str]) -> list[dict[str, str]]:
    expected_note = "该问题在资料中「不可回答」，期望模型明确说明资料不足。"
    if case.answerable:
        expected_note = "该问题在资料中「可回答」，期望模型基于资料给出准确答案。"

    content = (
        f"问题：{case.question}\n\n"
        f"模型回答：{answer}\n\n"
        f"检索到的资料：\n{''.join(contexts)}\n\n"
        f"{expected_note}"
    )
    return [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def _extract_score(text: str) -> int | None:
    match = re.search(r'"score"\s*:\s*(\d+)', text)
    if match:
        return int(match.group(1))
    return None


def _extract_correct(text: str) -> bool | None:
    match = re.search(r'"correct"\s*:\s*(true|false)', text, re.IGNORECASE)
    if match:
        return match.group(1).lower() == "true"
    return None


def _extract_reason(text: str) -> str:
    match = re.search(r'"reason"\s*:\s*"([^"]*)"', text)
    if match:
        return match.group(1)
    return ""


async def _generate_answer(question: str) -> tuple[str, list[str]]:
    events = []
    async for event in stream_rag_answer(question=question, top_k=5):
        events.append(event)

    answer_parts: list[str] = []
    contexts: list[str] = []
    for event in events:
        if event.get("event") == "delta":
            answer_parts.append(str(event["data"].get("content") or ""))
        elif event.get("event") == "sources":
            for source in event["data"].get("sources", []):
                contexts.append(
                    f"[文档：{source.get('document_title') or source.get('source_path')}]\n"
                    f"{source.get('content', '')}\n"
                )

    return "".join(answer_parts), contexts


async def _judge_answer(
    case: EvaluationCase,
    answer: str,
    contexts: list[str],
    judge_client: OpenAIChatClient,
) -> dict[str, object]:
    messages = _build_judge_messages(case, answer, contexts)
    try:
        raw = await judge_client.chat(messages, temperature=0.0)
    except Exception as exc:
        return {"correct": False, "score": 1, "reason": f"评测失败: {exc}"}

    score = _extract_score(raw) or 1
    correct = _extract_correct(raw) or (score >= 4)
    reason = _extract_reason(raw) or raw[:100]
    return {"correct": correct, "score": score, "reason": reason}


async def _evaluate_case(
    case: EvaluationCase,
    judge_client: OpenAIChatClient,
) -> dict[str, object]:
    answer, contexts = await _generate_answer(case.question)
    judgment = await _judge_answer(case, answer, contexts, judge_client)

    return {
        "id": case.id,
        "question": case.question,
        "answerable": case.answerable,
        "answer": answer,
        "correct": judgment["correct"],
        "score": judgment["score"],
        "reason": judgment["reason"],
        "context_count": len(contexts),
    }


async def evaluate_rag_answers(
    cases: list[EvaluationCase],
    judge_client: OpenAIChatClient | None = None,
) -> dict[str, object]:
    judge_client = judge_client or OpenAIChatClient()

    case_reports = []
    for case in cases:
        report = await _evaluate_case(case, judge_client)
        case_reports.append(report)

    answerable = [r for r in case_reports if r["answerable"]]
    unanswerable = [r for r in case_reports if not r["answerable"]]

    def accuracy(items: list[dict[str, object]]) -> float:
        if not items:
            return 0.0
        return sum(1 for r in items if r["correct"]) / len(items)

    def avg_score(items: list[dict[str, object]]) -> float | None:
        if not items:
            return None
        return round(mean(r["score"] for r in items), 2)

    return {
        "total_cases": len(case_reports),
        "answerable_cases": len(answerable),
        "unanswerable_cases": len(unanswerable),
        "overall_accuracy": round(accuracy(case_reports), 4),
        "answerable_accuracy": round(accuracy(answerable), 4),
        "unanswerable_accuracy": round(accuracy(unanswerable), 4),
        "overall_avg_score": avg_score(case_reports),
        "answerable_avg_score": avg_score(answerable),
        "unanswerable_avg_score": avg_score(unanswerable),
        "cases": case_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate KnowRAG end-to-end answer accuracy.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "retrieval_seed.jsonl",
        help="JSONL evaluation dataset path.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON report output path.")
    args = parser.parse_args()

    cases = load_evaluation_cases(args.dataset)
    report = asyncio.run(evaluate_rag_answers(cases))

    output_path = args.output or _default_report_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Dataset: {args.dataset}")
    print(f"Cases: {report['total_cases']} (answerable={report['answerable_cases']}, unanswerable={report['unanswerable_cases']})")
    print(f"Overall accuracy: {report['overall_accuracy']:.2%}")
    print(f"Answerable accuracy: {report['answerable_accuracy']:.2%}")
    print(f"Unanswerable accuracy: {report['unanswerable_accuracy']:.2%}")
    print(f"Average score: {report['overall_avg_score']}")
    print(f"Report: {output_path}")
    return 0


def _default_report_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_ROOT / "evaluation" / "reports" / f"rag-answer-{timestamp}.json"


if __name__ == "__main__":
    raise SystemExit(main())
