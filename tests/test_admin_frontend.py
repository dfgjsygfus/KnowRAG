import unittest
from html.parser import HTMLParser
from pathlib import Path


ADMIN_HTML = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
ADMIN_SCRIPT = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


class AdminFrontendTest(unittest.TestCase):
    def test_file_input_is_not_nested_inside_upload_zone(self):
        parser = UploadStructureParser()
        parser.feed(ADMIN_HTML.read_text(encoding="utf-8"))

        self.assertTrue(parser.found_file_input)
        self.assertFalse(parser.file_input_inside_upload_zone)

    def test_upload_reloads_authoritative_document_list(self):
        script = ADMIN_SCRIPT.read_text(encoding="utf-8")

        upload_block = script[script.index("function handleFiles"):script.index("async function indexFile")]
        self.assertIn("await loadDocuments();", upload_block)
        self.assertNotIn("files.unshift(normalizeDocument(document));", upload_block)
        self.assertIn("document.deduplicated", upload_block)

    def test_admin_console_exposes_chat_model_settings_view(self):
        html = ADMIN_HTML.read_text(encoding="utf-8")
        script = ADMIN_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('id="nav-settings"', html)
        self.assertIn("showSettingsView", script)
        self.assertIn('apiFetch("/api/settings/chat-model"', script)
        self.assertIn('apiFetch("/api/settings/chat-model/test"', script)
        self.assertIn("chat-model-provider", script)
        self.assertIn("chat-model-test", script)
        self.assertIn('option value="custom"', script)
        self.assertIn("api_key_set", script)
        self.assertIn("profiles", script)
        self.assertNotIn("chatSettings.api_key = result.api_key", script)


class UploadStructureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.element_stack = []
        self.found_file_input = False
        self.file_input_inside_upload_zone = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id", "")
        self.element_stack.append(element_id)
        if element_id == "file-input":
            self.found_file_input = True
            self.file_input_inside_upload_zone = "upload-zone" in self.element_stack

    def handle_startendtag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id") == "file-input":
            self.found_file_input = True
            self.file_input_inside_upload_zone = "upload-zone" in self.element_stack

    def handle_endtag(self, tag):
        if self.element_stack:
            self.element_stack.pop()


if __name__ == "__main__":
    unittest.main()
