export const PET_SCALE_STEPS = [0.8, 1, 1.2, 1.4];
export const DEFAULT_PET_SCALE = 1;
export const PET_BASE_SIZE = 80;

const DEFAULT_EXPANDED_WIDTH = 588;
const DEFAULT_EXPANDED_HEIGHT = 540;
const DEFAULT_BUBBLE_WIDTH = 478;
const DEFAULT_BUBBLE_HEIGHT = 390;
const COLLAPSED_CHROME = 72;
const EXPANDED_WIDTH_CHROME = 508;
const BUBBLE_WIDTH_CHROME = 398;

export function getNextPetScale(currentScale, direction) {
  const currentIndex = PET_SCALE_STEPS.findIndex((scale) => scale >= currentScale);
  const fallbackIndex = PET_SCALE_STEPS.indexOf(DEFAULT_PET_SCALE);
  const startIndex = currentIndex === -1 ? fallbackIndex : currentIndex;
  const nextIndex = Math.min(Math.max(startIndex + Math.sign(direction), 0), PET_SCALE_STEPS.length - 1);

  return PET_SCALE_STEPS[nextIndex];
}

export function getPetSize(scale) {
  return Math.round(PET_BASE_SIZE * scale);
}

export function getPetWindowSize(chatSurface, scale) {
  const petSize = getPetSize(scale);

  if (chatSurface === "full") {
    return {
      width: Math.max(DEFAULT_EXPANDED_WIDTH, petSize + EXPANDED_WIDTH_CHROME),
      height: DEFAULT_EXPANDED_HEIGHT,
    };
  }

  if (chatSurface === "bubble") {
    return {
      width: Math.max(DEFAULT_BUBBLE_WIDTH, petSize + BUBBLE_WIDTH_CHROME),
      height: DEFAULT_BUBBLE_HEIGHT,
    };
  }

  // "pet"
  return {
    width: petSize + COLLAPSED_CHROME,
    height: petSize + COLLAPSED_CHROME,
  };
}

export function getPositionKeepingBottomRight(oldPosition, oldSize, nextSize) {
  return {
    x: oldPosition.x - (nextSize.width - oldSize.width),
    y: oldPosition.y - (nextSize.height - oldSize.height),
  };
}

export function getPetAnchorOffset(surface, scale, windowSize) {
  const shellSize = getPetSize(scale) + 36;

  if (surface === "pet") {
    return {
      x: windowSize.width / 2,
      y: windowSize.height / 2,
    };
  }

  // bubble or full: pet is on the right side, vertically centered
  return {
    x: windowSize.width - 18 - shellSize / 2,
    y: windowSize.height / 2,
  };
}

export function getPositionKeepingPetAnchor(oldPosition, oldAnchor, nextAnchor) {
  return {
    x: oldPosition.x + oldAnchor.x - nextAnchor.x,
    y: oldPosition.y + oldAnchor.y - nextAnchor.y,
  };
}
