import unittest

from backend.app.schemas.ingestion import ChunkingConfig, CleanedDocument, MarkdownSection
from backend.app.services.document_chunker import chunk_cleaned_document
from backend.app.services.markdown_cleaner import clean_markdown_document


class DocumentChunkerTest(unittest.TestCase):
    def test_builds_chunks_with_document_and_section_metadata(self):
        document = clean_markdown_document(
            """# Root

Intro paragraph with useful context.

## Child

This section contains enough text to become a retrievable chunk.
""",
            source_path="demo.md",
        )

        result = chunk_cleaned_document(document, ChunkingConfig(max_tokens=80, min_tokens=10))

        self.assertEqual(result.source_path, "demo.md")
        self.assertGreaterEqual(len(result.chunks), 1)
        chunk = result.chunks[0]
        self.assertEqual(chunk.source_path, "demo.md")
        self.assertEqual(chunk.document_title, "Root")
        self.assertEqual(chunk.chunk_index, 0)
        self.assertGreaterEqual(chunk.token_count, 1)
        self.assertTrue(chunk.content.strip())
        self.assertTrue(chunk.heading_path)

    def test_merges_short_sections_with_following_content(self):
        document = CleanedDocument(
            source_path="demo.md",
            title="Root",
            cleaned_text="",
            sections=[
                MarkdownSection(
                    heading="Tiny",
                    heading_path=("Root", "Tiny"),
                    level=2,
                    content="## Tiny\nShort.",
                    start_line=1,
                    end_line=2,
                ),
                MarkdownSection(
                    heading="Details",
                    heading_path=("Root", "Details"),
                    level=2,
                    content="## Details\n" + "Detailed content. " * 10,
                    start_line=3,
                    end_line=8,
                ),
            ],
        )

        result = chunk_cleaned_document(document, ChunkingConfig(max_tokens=120, min_tokens=20))

        self.assertEqual(len(result.chunks), 1)
        self.assertIn("Short.", result.chunks[0].content)
        self.assertIn("Detailed content.", result.chunks[0].content)
        self.assertEqual(result.chunks[0].section_indexes, (0, 1))

    def test_splits_long_sections_on_paragraph_boundaries(self):
        paragraphs = [f"Paragraph {i} " + "word " * 18 for i in range(8)]
        document = clean_markdown_document(
            "# Root\n\n## Long\n\n" + "\n\n".join(paragraphs),
            source_path="long.md",
        )

        result = chunk_cleaned_document(document, ChunkingConfig(max_tokens=45, min_tokens=5, overlap_tokens=0))

        self.assertGreater(len(result.chunks), 1)
        self.assertTrue(all(chunk.token_count <= 55 for chunk in result.chunks))
        self.assertTrue(all(chunk.heading_path == ("Root", "Long") for chunk in result.chunks[1:]))

    def test_keeps_code_blocks_intact_when_splitting(self):
        document = clean_markdown_document(
            """# Root

## Code

Intro text before code.

```python
def alpha():
    return "a"
```

More explanation after code.
""",
            source_path="code.md",
        )

        result = chunk_cleaned_document(document, ChunkingConfig(max_tokens=12, min_tokens=1, overlap_tokens=0))

        code_chunks = [chunk for chunk in result.chunks if "def alpha" in chunk.content]
        self.assertEqual(len(code_chunks), 1)
        self.assertIn("```python", code_chunks[0].content)
        self.assertIn('return "a"', code_chunks[0].content)
        self.assertIn("```", code_chunks[0].content)

    def test_same_filename_in_different_paths_gets_distinct_chunk_ids(self):
        first = clean_markdown_document("# Root\n\nFirst content.", source_path="team-a/demo.md")
        second = clean_markdown_document("# Root\n\nSecond content.", source_path="team-b/demo.md")

        first_chunk = chunk_cleaned_document(first).chunks[0]
        second_chunk = chunk_cleaned_document(second).chunks[0]

        self.assertNotEqual(first_chunk.chunk_id, second_chunk.chunk_id)
        self.assertTrue(first_chunk.chunk_id.startswith("demo-"))
        self.assertTrue(second_chunk.chunk_id.startswith("demo-"))


if __name__ == "__main__":
    unittest.main()
