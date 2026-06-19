import assert from "node:assert/strict";
import test from "node:test";

import {
  canIndex,
  fileExt,
  formatRelativeTime,
  formatSize,
  statusClass,
  statusLabel,
} from "./format.js";

test("formatSize formats bytes", () => {
  assert.equal(formatSize(0), "0 B");
  assert.equal(formatSize(512), "512 B");
  assert.equal(formatSize(1536), "1.5 KB");
  assert.equal(formatSize(1024 * 1024), "1.00 MB");
});

test("formatRelativeTime returns relative labels", () => {
  const now = new Date();
  assert.equal(formatRelativeTime(now.toISOString()), "刚刚");
  assert.equal(formatRelativeTime(new Date(now.getTime() - 2 * 60 * 1000).toISOString()), "2 分钟前");
  assert.equal(formatRelativeTime(new Date(now.getTime() - 3 * 60 * 60 * 1000).toISOString()), "3 小时前");
  assert.equal(formatRelativeTime(null), "—");
  assert.equal(formatRelativeTime("invalid"), "invalid");
});

test("statusClass maps statuses", () => {
  assert.equal(statusClass("ready"), "ready");
  assert.equal(statusClass("indexing"), "indexing");
  assert.equal(statusClass("failed"), "failed");
  assert.equal(statusClass("uploaded"), "");
});

test("statusLabel maps statuses", () => {
  assert.equal(statusLabel("ready"), "已入库");
  assert.equal(statusLabel("uploaded"), "待入库");
  assert.equal(statusLabel("unknown"), "待入库");
});

test("fileExt extracts extension", () => {
  assert.equal(fileExt("README.md"), "md");
  assert.equal(fileExt("data"), "data");
  assert.equal(fileExt(""), "txt");
});

test("canIndex checks indexable statuses", () => {
  assert.equal(canIndex({ status: "uploaded" }), true);
  assert.equal(canIndex({ status: "failed" }), true);
  assert.equal(canIndex({ status: "ready" }), false);
  assert.equal(canIndex({ status: "indexing" }), false);
});
