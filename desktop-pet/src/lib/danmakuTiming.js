export const DANMAKU_FADE_MIN_MS = 5000;
export const DANMAKU_FADE_MAX_MS = 30000;
export const DANMAKU_FADE_PER_CHAR_MS = 40;

export function computeDanmakuLifespan(content) {
  const length = typeof content === "string" ? content.length : 0;
  const raw = DANMAKU_FADE_MIN_MS + length * DANMAKU_FADE_PER_CHAR_MS;
  return Math.min(DANMAKU_FADE_MAX_MS, raw);
}
