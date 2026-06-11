import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_PET_SCALE,
  getNextPetScale,
  getPetAnchorOffset,
  getPetSize,
  getPetWindowSize,
  getPositionKeepingBottomRight,
  getPositionKeepingPetAnchor,
  PET_SCALE_STEPS,
} from "./petScale.js";

test("getNextPetScale walks fixed scale steps and clamps at both ends", () => {
  assert.deepEqual(PET_SCALE_STEPS, [0.8, 1, 1.2, 1.4]);
  assert.equal(DEFAULT_PET_SCALE, 1);

  assert.equal(getNextPetScale(1, 1), 1.2);
  assert.equal(getNextPetScale(1.2, 1), 1.4);
  assert.equal(getNextPetScale(1.4, 1), 1.4);
  assert.equal(getNextPetScale(1, -1), 0.8);
  assert.equal(getNextPetScale(0.8, -1), 0.8);
});

test("getPetWindowSize keeps the pet visible across all three surface modes", () => {
  assert.equal(getPetSize(1), 80);
  assert.deepEqual(getPetWindowSize("pet", 1), { width: 152, height: 152 });
  assert.deepEqual(getPetWindowSize("bubble", 1), { width: 478, height: 390 });
  assert.deepEqual(getPetWindowSize("full", 1), { width: 588, height: 540 });

  assert.equal(getPetSize(1.4), 112);
  assert.deepEqual(getPetWindowSize("pet", 1.4), { width: 184, height: 184 });
  assert.deepEqual(getPetWindowSize("bubble", 1.4), { width: 510, height: 390 });
  assert.deepEqual(getPetWindowSize("full", 1.4), { width: 620, height: 540 });
});

test("getPositionKeepingBottomRight offsets position by the size delta", () => {
  assert.deepEqual(
    getPositionKeepingBottomRight(
      { x: 1200, y: 600 },
      { width: 152, height: 152 },
      { width: 588, height: 540 },
    ),
    { x: 764, y: 212 },
  );

  assert.deepEqual(
    getPositionKeepingBottomRight(
      { x: 764, y: 212 },
      { width: 588, height: 540 },
      { width: 152, height: 152 },
    ),
    { x: 1200, y: 600 },
  );
});

test("getPetAnchorOffset returns window center for pet surface and right-side for bubble/full", () => {
  // pet surface at scale 1.0: window 152×152, anchor = center
  assert.deepEqual(
    getPetAnchorOffset("pet", 1, { width: 152, height: 152 }),
    { x: 76, y: 76 },
  );

  // bubble surface at scale 1.0: window 478×390
  // shellSize = 80 + 36 = 116, anchor = (478 - 18 - 58, 195)
  assert.deepEqual(
    getPetAnchorOffset("bubble", 1, { width: 478, height: 390 }),
    { x: 402, y: 195 },
  );

  // full surface at scale 1.0: window 588×540
  assert.deepEqual(
    getPetAnchorOffset("full", 1, { width: 588, height: 540 }),
    { x: 512, y: 270 },
  );

  // pet surface at scale 1.4: window 184×184, anchor = center
  assert.deepEqual(
    getPetAnchorOffset("pet", 1.4, { width: 184, height: 184 }),
    { x: 92, y: 92 },
  );

  // full surface at scale 1.4: window 620×540
  // petSize = 112, shellSize = 148, anchor x = 620 - 18 - 74 = 528
  assert.deepEqual(
    getPetAnchorOffset("full", 1.4, { width: 620, height: 540 }),
    { x: 528, y: 270 },
  );
});

test("getPositionKeepingPetAnchor keeps pet screen position fixed", () => {
  // pet (152×152) → full (588×540): pet should stay at same screen coords
  // pet anchor = (76, 76), full anchor = (512, 270)
  assert.deepEqual(
    getPositionKeepingPetAnchor(
      { x: 1200, y: 600 },
      { x: 76, y: 76 },
      { x: 512, y: 270 },
    ),
    { x: 764, y: 406 },
  );

  // Verify round-trip: the pet screen position (1276, 676) is preserved
  // After expanding: 764 + 512 = 1276, 406 + 270 = 676 ✓
  assert.deepEqual(
    getPositionKeepingPetAnchor(
      { x: 764, y: 406 },
      { x: 512, y: 270 },
      { x: 76, y: 76 },
    ),
    { x: 1200, y: 600 },
  );
});

test("getPositionKeepingPetAnchor handles scale change without anchor drift", () => {
  // pet scale 1.0 → 1.4 in pet mode: window 152×152 → 184×184
  // old anchor = (76, 76), new anchor = (92, 92)
  // Window expands by 32px in both directions, centered on pet → moves by 16px each
  assert.deepEqual(
    getPositionKeepingPetAnchor(
      { x: 500, y: 400 },
      { x: 76, y: 76 },
      { x: 92, y: 92 },
    ),
    { x: 484, y: 384 },
  );

  // full mode scale 1.0 → 1.4: window 588×540 → 620×540
  // old anchor = (512, 270), new anchor = (528, 270)
  assert.deepEqual(
    getPositionKeepingPetAnchor(
      { x: 300, y: 200 },
      { x: 512, y: 270 },
      { x: 528, y: 270 },
    ),
    { x: 284, y: 200 },
  );
});
