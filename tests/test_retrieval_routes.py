import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


class RetrievalRoutesTest(unittest.TestCase):
    def test_search_route_returns_retrieval_results(self):
        with patch(
            "backend.app.api.retrieval.retrieve_query_payload",
            return_value={
                "query": "Prompt 设计是什么？",
                "top_k": 5,
                "collection_name": "knowrag_chunks",
                "total": 1,
                "results": [
                    {
                        "chunk_id": "demo:0000",
                        "score": 0.82,
                        "document_title": "Root",
                        "source_path": "docs/demo.md",
                        "heading_path": ["Root", "Prompt 设计"],
                        "content": "PLANNING_PROMPT 用于生成研究大纲。",
                        "token_count": 20,
                        "start_line": 1,
                        "end_line": 8,
                    }
                ],
            },
        ):
            response = client.post(
                "/api/retrieval/search",
                json={"query": "Prompt 设计是什么？", "top_k": 5},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["query"], "Prompt 设计是什么？")
        self.assertEqual(body["results"][0]["chunk_id"], "demo:0000")
        self.assertEqual(body["results"][0]["heading_path"], ["Root", "Prompt 设计"])


if __name__ == "__main__":
    unittest.main()
