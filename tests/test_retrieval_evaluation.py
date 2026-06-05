import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.app.schemas.retrieval import RetrievalResult, RetrievalSearchResult
from backend.app.services.retrieval_evaluation import (
    EvaluationDatasetError,
    evaluate_retrieval,
    load_evaluation_cases,
)


class RetrievalEvaluationTest(unittest.TestCase):
    def test_loads_valid_jsonl_cases(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cases.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "id": "case-1",
                        "question": "Prompt 如何设计？",
                        "answerable": True,
                        "expected_source_paths": ["docs/chief.md"],
                        "expected_heading_keywords": ["Prompt"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            cases = load_evaluation_cases(path)

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].id, "case-1")
        self.assertEqual(cases[0].expected_heading_keywords, ("Prompt",))

    def test_rejects_answerable_case_without_expected_match_rules(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid.jsonl"
            path.write_text(
                '{"id":"case-1","question":"问题","answerable":true}\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(EvaluationDatasetError, "line 1"):
                load_evaluation_cases(path)

    def test_computes_recall_mrr_and_recommended_threshold(self):
        cases = _cases()
        results = {
            "hit-at-two": _retrieval(
                _hit("wrong", 0.95, "docs/other.md", ("Other",)),
                _hit("correct", 0.90, "docs/chief.md", ("Prompt 设计",)),
            ),
            "miss": _retrieval(_hit("wrong", 0.70, "docs/chief.md", ("模型选择策略",))),
            "outside": _retrieval(_hit("noise", 0.40, "docs/chief.md", ("总结",))),
        }

        report = evaluate_retrieval(cases, lambda question, top_k: results[question], top_k=2)

        self.assertEqual(report["total_cases"], 3)
        self.assertEqual(report["answerable_cases"], 2)
        self.assertEqual(report["unanswerable_cases"], 1)
        self.assertEqual(report["recall_at_k"], 0.5)
        self.assertEqual(report["mrr"], 0.25)
        self.assertEqual(report["recommended_min_score"], 0.7)
        self.assertEqual(report["errors"], 0)

    def test_continues_when_one_retrieval_fails(self):
        cases = _cases()[:2]

        def retrieve(question, top_k):
            if question == "miss":
                raise RuntimeError("milvus unavailable")
            return _retrieval(_hit("correct", 0.9, "docs/chief.md", ("Prompt 设计",)))

        report = evaluate_retrieval(cases, retrieve, top_k=5)

        self.assertEqual(report["errors"], 1)
        self.assertEqual(report["cases"][1]["error"], "milvus unavailable")
        self.assertEqual(report["recall_at_k"], 0.5)
        self.assertEqual(report["answerable_top_scores"], [0.9])

    def test_heading_keyword_can_match_retrieved_chunk_content(self):
        cases = _cases()[:1]
        retrieval = _retrieval(
            RetrievalSearchResult(
                chunk_id="merged",
                score=0.88,
                document_title="ChiefArchitect",
                source_path="docs/chief.md",
                heading_path=("职责定位", "代码实现"),
                content="前文介绍了 Prompt 设计与 PLANNING_PROMPT。",
                token_count=10,
                start_line=1,
                end_line=2,
            )
        )

        report = evaluate_retrieval(cases, lambda question, top_k: retrieval, top_k=5)

        self.assertEqual(report["recall_at_k"], 1.0)
        self.assertEqual(report["cases"][0]["first_relevant_rank"], 1)


def _cases():
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "cases.jsonl"
        rows = [
            {
                "id": "case-hit",
                "question": "hit-at-two",
                "answerable": True,
                "expected_source_paths": ["docs/chief.md"],
                "expected_heading_keywords": ["Prompt"],
            },
            {
                "id": "case-miss",
                "question": "miss",
                "answerable": True,
                "expected_source_paths": ["docs/chief.md"],
                "expected_heading_keywords": ["职责定位"],
            },
            {
                "id": "case-outside",
                "question": "outside",
                "answerable": False,
            },
        ]
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
        return load_evaluation_cases(path)


def _retrieval(*hits):
    return RetrievalResult(
        query="query",
        top_k=5,
        collection_name="knowrag_chunks",
        total=len(hits),
        results=list(hits),
    )


def _hit(chunk_id, score, source_path, heading_path):
    return RetrievalSearchResult(
        chunk_id=chunk_id,
        score=score,
        document_title="ChiefArchitect",
        source_path=source_path,
        heading_path=heading_path,
        content="content",
        token_count=10,
        start_line=1,
        end_line=2,
    )


if __name__ == "__main__":
    unittest.main()
