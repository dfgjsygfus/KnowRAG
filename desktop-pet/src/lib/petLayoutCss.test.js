import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const styleCss = readFileSync(new URL("../style.css", import.meta.url), "utf8");
const petMainVue = readFileSync(new URL("../components/PetMain.vue", import.meta.url), "utf8");
const petAssetLicenseUrl = new URL("../assets/pet-asset-license.txt", import.meta.url);
const petAnimationFramesJs = readFileSync(new URL("./petAnimationFrames.js", import.meta.url), "utf8");
const fullChatPanelVue = readFileSync(new URL("../components/FullChatPanel.vue", import.meta.url), "utf8");

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

test("pet character uses generated frame sequences instead of the old canvas sprite", () => {
  assert.match(petMainVue, /getPetAnimationFrames/);
  assert.match(petMainVue, /const petFrameImage = computed/);
  assert.match(petMainVue, /<img[\s\S]*class="pet-character"[\s\S]*:src="petFrameImage"/);
  assert.doesNotMatch(petMainVue, /<canvas/);
  assert.doesNotMatch(petMainVue, /function drawPet/);
});

test("pet has separate idle and thoughtful thinking frame playback", () => {
  assert.match(petMainVue, /idle:\s*!isWorking && !isFailure && !isNoResult/);
  assert.match(petMainVue, /getPetAnimationFrames/);
  assert.match(petMainVue, /setInterval\(\(\) => \{/);

  assert.match(styleCss, /\.pet-character/);
  assert.match(styleCss, /\.pet-shell\.thinking\s+\.pet-character/);
});

test("pet character assets keep the downloaded source license with frame-count contract", () => {
  assert.equal((petAnimationFramesJs.match(/pet-girl-idle-\d+\.png/g) ?? []).length, 8);
  assert.equal((petAnimationFramesJs.match(/pet-girl-thinking-\d+\.png/g) ?? []).length, 4);
  assert.ok(existsSync(petAssetLicenseUrl), "downloaded pet asset license should be checked in");

  const licenseText = readFileSync(petAssetLicenseUrl, "utf8");
  assert.match(licenseText, /Kenney/);
  assert.match(licenseText, /Toon Characters/);
  assert.match(licenseText, /Creative Commons Zero|CC0/);
});

test("full chat branding does not use the old dog pet name, greeting, or emoji", () => {
  assert.doesNotMatch(petMainVue, /旺财/);
  assert.doesNotMatch(petMainVue, /汪/);
  assert.doesNotMatch(petMainVue, /🐶/);
});

test("full chat submit calls submitQuestion without passing the native DOM event", () => {
  assert.match(fullChatPanelVue, /<form class="fc-input-row" @submit\.prevent="submitQuestion">/);
  assert.match(fullChatPanelVue, /@keydown\.enter\.exact\.prevent="submitQuestion"/);
  assert.doesNotMatch(fullChatPanelVue, /@submit\.prevent="submitQuestion\(/);
  assert.doesNotMatch(fullChatPanelVue, /@keydown\.enter\.exact\.prevent="submitQuestion\(/);
});

test("full chat panel is extracted from the pet window orchestrator", () => {
  assert.match(petMainVue, /<FullChatPanel/);
  assert.match(petMainVue, /@submit="askQuestion"/);
  assert.match(petMainVue, /@close="closeToPet"/);
  assert.doesNotMatch(petMainVue, /class="fc-input-row"/);
  assert.match(fullChatPanelVue, /class="fc-input-row"/);
  assert.match(fullChatPanelVue, /emit\("submit"/);
});
