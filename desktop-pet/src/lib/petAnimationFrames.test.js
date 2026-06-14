import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("./petAnimationFrames.js", import.meta.url), "utf8");

test("pet animation frame sets keep the desktop pet contract", () => {
  assert.equal((source.match(/pet-girl-idle-\d+\.png/g) ?? []).length, 8);
  assert.equal((source.match(/pet-girl-thinking-\d+\.png/g) ?? []).length, 4);
  assert.match(source, /export const PET_FRAME_INTERVAL_MS = 220;/);
});

test("getPetAnimationFrames chooses thinking frames only while working", () => {
  assert.match(source, /export function getPetAnimationFrames\(isWorking\)/);
  assert.match(source, /return isWorking \? thinkingPetFrames : idlePetFrames/);
});
