export const PET_SCALE_STEPS = [0.8, 1, 1.2, 1.4];
export const DEFAULT_PET_SCALE = 1;
export const PET_BASE_SIZE = 80;

const DEFAULT_EXPANDED_WIDTH = 588;
const DEFAULT_EXPANDED_HEIGHT = 540;
const DEFAULT_LIGHT_WIDTH = 300;
const DEFAULT_LIGHT_HEIGHT = 380;
const COLLAPSED_CHROME = 72;
const HOVER_HINT_CHROME = 108;
const EXPANDED_WIDTH_CHROME = 508;

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

export function getPetWindowSize(chatSurface, scale, options = {}) {
  const petSize = getPetSize(scale);

  if (chatSurface === "full") {
    return {
      width: Math.max(DEFAULT_EXPANDED_WIDTH, petSize + EXPANDED_WIDTH_CHROME),
      height: DEFAULT_EXPANDED_HEIGHT,
    };
  }

  if (chatSurface === "light") {
    return {
      width: Math.max(DEFAULT_LIGHT_WIDTH, petSize + 220),
      height: Math.max(DEFAULT_LIGHT_HEIGHT, petSize + 300),
    };
  }

  if (chatSurface === "pet" && options.reserveFloatingAnswer) {
    return {
      width: Math.max(DEFAULT_LIGHT_WIDTH, petSize + 220),
      height: Math.max(DEFAULT_LIGHT_HEIGHT, petSize + 300),
    };
  }

  // "pet"
  return {
    width: petSize + COLLAPSED_CHROME,
    height: petSize + HOVER_HINT_CHROME,
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

  // light: pet is centered horizontally, but sits above vertical centre
  // because the input row below shifts the flex group centre downward.
  // pet is offset by -(gap + inputRowHeight) / 2 = -(10 + 34) / 2 = -22 px
  if (surface === "light") {
    return {
      x: windowSize.width / 2,
      y: windowSize.height / 2 - 22,
    };
  }

  // full: pet is on the right side, vertically centered
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
