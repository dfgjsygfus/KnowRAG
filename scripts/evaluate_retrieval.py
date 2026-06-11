from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.retrieval_evaluation import evaluate_retrieval, load_evaluation_cases
from backend.app.services.retrieval_service import retrieve_query


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate KnowRAG retrieval quality.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "retrieval_seed.jsonl",
        help="JSONL evaluation dataset path.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieval results per question.")
    parser.add_argument("--output", type=Path, help="Optional JSON report output path.")
    args = parser.parse_args()

    if args.top_k < 1:
        parser.error("--top-k must be at least 1")

    cases = load_evaluation_cases(args.dataset)
    report = evaluate_retrieval(cases, retrieve_query, top_k=args.top_k)
    output_path = args.output or _default_report_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Dataset: {args.dataset}")
    print(f"Cases: {report['total_cases']} | Errors: {report['errors']}")
    print(f"Evaluation valid: {report['valid']} | Error rate: {report['error_rate']:.4f}")
    print(f"Recall@{args.top_k}: {report['recall_at_k']:.4f}")
    print(f"MRR: {report['mrr']:.4f}")
    print(f"Recommended RAG_MIN_SCORE: {report['recommended_min_score']}")
    print(f"Report: {output_path}")
    return 0 if report["valid"] else 2


def _default_report_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_ROOT / "evaluation" / "reports" / f"retrieval-{timestamp}.json"


if __name__ == "__main__":
    raise SystemExit(main())
