import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const styleCss = readFileSync(new URL("../style.css", import.meta.url), "utf8");
const petMainVue = readFileSync(new URL("../components/PetMain.vue", import.meta.url), "utf8");

function cssRule(selector) {
  const match = styleCss.match(new RegExp(`${selector.replaceAll(".", "\\.")}\\s*\\{([^}]*)\\}`));
  assert.ok(match, `${selector} rule should exist`);
  return match[1];
}

test("hover bubble is positioned relative to the pet, not the window bottom", () => {
  const hoverBubbleRule = cssRule(".pet-hover-bubble");

  assert.match(hoverBubbleRule, /top:\s*calc\(50%\s*\+\s*var\(--pet-shell-size/);
  assert.doesNotMatch(hoverBubbleRule, /bottom:/);
  assert.match(petMainVue, /<main\s+class="pet-window"[^>]*:style="petStyle"/);
});

test("hover bubble visibility does not resize the native window", () => {
  assert.match(petMainVue, /reserveFloatingAnswer:\s*surface === "pet" && danmakuVisible\.value/);
  assert.doesNotMatch(petMainVue, /hoverBubble\.value = true;\s*void resizeWindow\(\);/);
  assert.doesNotMatch(petMainVue, /hoverBubble\.value = false;\s*void resizeWindow\(\);/);
  assert.doesNotMatch(petMainVue, /danmakuVisible\.value\s*\|\|\s*hoverBubble\.value/);
});

test("light chat input is not mounted in the main pet window", () => {
  assert.doesNotMatch(petMainVue, /v-show="chatSurface === 'light'"/);
  assert.match(petMainVue, /openPetChatWindow/);
  assert.match(petMainVue, /listen\("pet-chat-submit"/);
});

test("hover ask bubble stays hidden while the standalone input is open", () => {
  assert.match(petMainVue, /v-show="chatSurface === 'pet' && !isChatInputOpen"/);
  assert.match(petMainVue, /if \(chatSurface\.value !== "pet" \|\| isChatInputOpen\.value\) return;/);
});

test("standalone input follows the pet window while it moves", () => {
  assert.match(petMainVue, /onMoved\(\(\) => \{/);
  assert.match(petMainVue, /if \(isChatInputOpen\.value\) void positionChatInput\(\);/);
  assert.match(petMainVue, /bringToFront:\s*true/);
});

test("pet-mode floating answers resize before showing and shrink after completion", () => {
  assert.match(petMainVue, /function showDanmaku\(\)\s*\{[\s\S]*if \(chatSurface\.value === "pet"\) \{[\s\S]*void resizeWindow\(\);/);
  assert.match(petMainVue, /if \(event === "done"\) \{[\s\S]*scheduleDanmakuFadeOut\(\);/);
  assert.match(petMainVue, /if \(event === "error"\) \{[\s\S]*scheduleDanmakuFadeOut\(\);/);
});
