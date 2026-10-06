import { useWindowSize } from "usehooks-ts";

export const STAGE = { width: 1920, height: 1080 } as const;
export const SAFE = { x: 96, y: 204, width: 1728, height: 564 } as const;

/** Scale factor that fits the 1920x1080 stage into the viewport, letterboxed. */
export function useStageScale(): number {
  const { width, height } = useWindowSize({ initializeWithValue: true });
  if (!width || !height) return 1;
  return Math.min(width / STAGE.width, height / STAGE.height);
}
