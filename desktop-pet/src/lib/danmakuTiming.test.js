import assert from "node:assert/strict";
import test from "node:test";

import { computeDanmakuLifespan, DANMAKU_FADE_MIN_MS, DANMAKU_FADE_MAX_MS } from "./danmakuTiming.js";

test("computeDanmakuLifespan returns the minimum for empty or undefined content", () => {
  assert.equal(computeDanmakuLifespan(""), DANMAKU_FADE_MIN_MS);
  assert.equal(computeDanmakuLifespan(undefined), DANMAKU_FADE_MIN_MS);
  assert.equal(computeDanmakuLifespan(null), DANMAKU_FADE_MIN_MS);
});

test("computeDanmakuLifespan grows linearly with content length", () => {
  // 10 字 → 5000 + 10*40 = 5400
  assert.equal(computeDanmakuLifespan("一二三四五六七八九十"), 5400);
  // 150 字 → 5000 + 150*40 = 11000
  assert.equal(computeDanmakuLifespan("x".repeat(150)), 11000);
});

test("computeDanmakuLifespan caps at the maximum", () => {
  // 800 字 → 5000 + 800*40 = 37000 → 截到 30000
  assert.equal(computeDanmakuLifespan("x".repeat(800)), DANMAKU_FADE_MAX_MS);
  // 10000 字也只到 30s
  assert.equal(computeDanmakuLifespan("x".repeat(10000)), DANMAKU_FADE_MAX_MS);
});

test("computeDanmakuLifespan boundaries: 5s floor and 30s cap are exposed as constants", () => {
  assert.equal(DANMAKU_FADE_MIN_MS, 5000);
  assert.equal(DANMAKU_FADE_MAX_MS, 30000);
});
