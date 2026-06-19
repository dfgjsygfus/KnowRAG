import assert from "node:assert/strict";
import test from "node:test";

import { formatAssistantContent, renderMarkdown } from "./markdown.js";

test("renderMarkdown converts Markdown to HTML", () => {
  const html = renderMarkdown("# Hello\n\n- one\n- two");
  assert.match(html, /<h1[^>]*>Hello<\/h1>/);
  assert.match(html, /<ul>/);
  assert.match(html, /<li>one<\/li>/);
});

test("renderMarkdown sanitizes dangerous HTML", () => {
  const html = renderMarkdown("<script>alert(1)</script>");
  assert.doesNotMatch(html, /<script>/i);
});

test("renderMarkdown opens external links safely", () => {
  const html = renderMarkdown("[link](https://example.com)");
  const anchor = html.match(/<a[^>]*>/i)?.[0] || "";
  assert.match(anchor, /target="_blank"/);
  assert.match(anchor, /rel="noopener noreferrer"/);
});

test("formatAssistantContent pretty-prints a JSON object", () => {
  const result = formatAssistantContent('{"a":1,"b":[2,3]}');
  assert.equal(result, "```json\n{\n  \"a\": 1,\n  \"b\": [\n    2,\n    3\n  ]\n}\n```");
});

test("formatAssistantContent pretty-prints a JSON array", () => {
  const result = formatAssistantContent('[{"x":1},{"x":2}]');
  assert.equal(result, "```json\n[\n  {\n    \"x\": 1\n  },\n  {\n    \"x\": 2\n  }\n]\n```");
});

test("formatAssistantContent leaves plain text unchanged", () => {
  const text = "Hello, this is **bold** text.";
  assert.equal(formatAssistantContent(text), text);
});

test("formatAssistantContent leaves invalid JSON-like text unchanged", () => {
  const text = "{not really json}";
  assert.equal(formatAssistantContent(text), text);
});

test("formatAssistantContent trims whitespace before detecting JSON", () => {
  const result = formatAssistantContent('  \n{"ok":true}\n  ');
  assert.equal(result, "```json\n{\n  \"ok\": true\n}\n```");
});
