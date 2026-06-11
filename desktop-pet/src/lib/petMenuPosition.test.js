import assert from "node:assert/strict";
import test from "node:test";

import { getMenuPositionNearClick } from "./petMenuPosition.js";

const MENU_W = 360;
const MENU_H = 360;

// Primary monitor (0,0) – 1920×1080
const PRIMARY = { left: 0, top: 0, right: 1920, bottom: 1080 };

test("places menu at click position when it fits", () => {
  const result = getMenuPositionNearClick({
    clickX: 200,
    clickY: 300,
    menuWidth: MENU_W,
    menuHeight: MENU_H,
    monitorLeft: PRIMARY.left,
    monitorTop: PRIMARY.top,
    monitorRight: PRIMARY.right,
    monitorBottom: PRIMARY.bottom,
  });

  assert.equal(result.x, 200);
  assert.equal(result.y, 300);
});

test("flips left when menu overflows right monitor edge", () => {
  const result = getMenuPositionNearClick({
    clickX: 1600,
    clickY: 400,
    menuWidth: MENU_W,
    menuHeight: MENU_H,
    monitorLeft: PRIMARY.left,
    monitorTop: PRIMARY.top,
    monitorRight: PRIMARY.right,
    monitorBottom: PRIMARY.bottom,
  });

  // menu would end at 1600+360=1960 > 1920-8, so flip: 1600-360=1240
  assert.equal(result.x, 1240);
  assert.equal(result.y, 400);
});

test("flips up when menu overflows bottom monitor edge", () => {
  const result = getMenuPositionNearClick({
    clickX: 500,
    clickY: 900,
    menuWidth: MENU_W,
    menuHeight: MENU_H,
    monitorLeft: PRIMARY.left,
    monitorTop: PRIMARY.top,
    monitorRight: PRIMARY.right,
    monitorBottom: PRIMARY.bottom,
  });

  // menu would end at 900+360=1260 > 1080-8, so flip: 900-360=540
  assert.equal(result.y, 540);
  assert.equal(result.x, 500);
});

test("flips both axes when near the bottom-right corner", () => {
  const result = getMenuPositionNearClick({
    clickX: 1800,
    clickY: 900,
    menuWidth: MENU_W,
    menuHeight: MENU_H,
    monitorLeft: PRIMARY.left,
    monitorTop: PRIMARY.top,
    monitorRight: PRIMARY.right,
    monitorBottom: PRIMARY.bottom,
  });

  assert.equal(result.x, 1440); // 1800 - 360
  assert.equal(result.y, 540); // 900 - 360
});

test("clamps to monitor margin when flipping would push off-screen", () => {
  const result = getMenuPositionNearClick({
    clickX: 200,
    clickY: 200,
    menuWidth: MENU_W,
    menuHeight: MENU_H,
    monitorLeft: 0,
    monitorTop: 0,
    monitorRight: 400,
    monitorBottom: 400,
  });

  // Both flips applied and clamped to monitorLeft+8 / monitorTop+8
  assert.equal(result.x, 8);
  assert.equal(result.y, 8);
});

test("does not clamp when position is above monitor margin", () => {
  const result = getMenuPositionNearClick({
    clickX: 30,
    clickY: 30,
    menuWidth: MENU_W,
    menuHeight: MENU_H,
    monitorLeft: PRIMARY.left,
    monitorTop: PRIMARY.top,
    monitorRight: PRIMARY.right,
    monitorBottom: PRIMARY.bottom,
  });

  // x=30 > 0+8, y=30 > 0+8, no clamp needed
  assert.equal(result.x, 30);
  assert.equal(result.y, 30);
});

test("works on secondary monitor with non-zero origin (e.g. x=1920)", () => {
  // Pet on a 1920×1080 secondary monitor to the right of a 1920×1080 primary
  const SECONDARY = { left: 1920, top: 0, right: 3840, bottom: 1080 };

  const result = getMenuPositionNearClick({
    clickX: 2120, // 200px from left edge of secondary
    clickY: 300,
    menuWidth: MENU_W,
    menuHeight: MENU_H,
    monitorLeft: SECONDARY.left,
    monitorTop: SECONDARY.top,
    monitorRight: SECONDARY.right,
    monitorBottom: SECONDARY.bottom,
  });

  // Menu fits: no flip needed, position stays at click coords
  assert.equal(result.x, 2120);
  assert.equal(result.y, 300);
});

test("flips left on secondary monitor near right edge", () => {
  const SECONDARY = { left: 1920, top: 0, right: 3840, bottom: 1080 };

  const result = getMenuPositionNearClick({
    clickX: 3600, // near right edge of secondary
    clickY: 400,
    menuWidth: MENU_W,
    menuHeight: MENU_H,
    monitorLeft: SECONDARY.left,
    monitorTop: SECONDARY.top,
    monitorRight: SECONDARY.right,
    monitorBottom: SECONDARY.bottom,
  });

  // 3600+360=3960 > 3840-8, flip left: 3600-360=3240
  assert.equal(result.x, 3240);
  assert.equal(result.y, 400);
});

test("clamps to secondary monitor left edge", () => {
  const SECONDARY = { left: 1920, top: 0, right: 3840, bottom: 1080 };

  // Click is at 1922, but 1922 < 1920+8=1928, so clamped to margin
  const result = getMenuPositionNearClick({
    clickX: 1922, // barely inside secondary
    clickY: 300,
    menuWidth: MENU_W,
    menuHeight: MENU_H,
    monitorLeft: SECONDARY.left,
    monitorTop: SECONDARY.top,
    monitorRight: SECONDARY.right,
    monitorBottom: SECONDARY.bottom,
  });

  // 1922 < 1920+8, so clamped to monitorLeft+MARGIN = 1928
  assert.equal(result.x, 1928);
  assert.equal(result.y, 300);
});
