from pathlib import Path
import unittest

from backend.app.schemas.ingestion import CleanedDocument, MarkdownSection
from backend.app.services.markdown_cleaner import clean_markdown_document


class MarkdownCleanerTest(unittest.TestCase):
    def test_removes_images_and_html_styles_while_preserving_content(self):
        markdown = """# Demo

![](<images/demo.png>)

**<span style="color: red">File path </span>**<span style="background: yellow">backend/app/main.py</span>

```python
def hello():
    return "world"
```
"""

        document = clean_markdown_document(markdown, source_path="demo.md")

        self.assertIsInstance(document, CleanedDocument)
        self.assertTrue(all(isinstance(section, MarkdownSection) for section in document.sections))
        self.assertNotIn("images/demo.png", document.cleaned_text)
        self.assertNotIn("<span", document.cleaned_text)
        self.assertIn("File path", document.cleaned_text)
        self.assertIn("backend/app/main.py", document.cleaned_text)
        self.assertIn("```python", document.cleaned_text)
        self.assertIn('return "world"', document.cleaned_text)

    def test_extracts_sections_with_heading_paths(self):
        markdown = """# Root

Intro paragraph.

## Child

- one
- two

### Grandchild

Details.
"""

        document = clean_markdown_document(markdown, source_path="demo.md")

        paths = [section.heading_path for section in document.sections]
        self.assertIn(("Root",), paths)
        self.assertIn(("Root", "Child"), paths)
        self.assertIn(("Root", "Child", "Grandchild"), paths)
        child = next(section for section in document.sections if section.heading_path == ("Root", "Child"))
        self.assertIn("- one", child.content)
        self.assertEqual(child.level, 2)

    def test_cleans_the_chief_architect_fixture_into_structured_sections(self):
        fixture = Path("docs/2.2.1 Agent - ChiefArchitect（总架构师）.md")

        document = clean_markdown_document(fixture.read_text(encoding="utf-8"), source_path=str(fixture))

        self.assertEqual(document.source_path, str(fixture))
        self.assertEqual(document.title, "1. 职责定位")
        self.assertGreater(len(document.cleaned_text), 1000)
        self.assertGreater(len(document.sections), 10)
        self.assertFalse(any("![](" in section.content for section in document.sections))
        self.assertFalse(any("<span" in section.content for section in document.sections))
        self.assertTrue(any("PLANNING_PROMPT" in section.content for section in document.sections))


if __name__ == "__main__":
    unittest.main()
