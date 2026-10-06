import { useWindowSize } from "usehooks-ts";

export interface StageGeometry {
  width: number;
  height: number;
  safe: { x: number; y: number; width: number; height: number };
}

/** The artwork's geometry, used until the bundle arrives with the admin's Display settings. */
export const DEFAULT_STAGE: StageGeometry = {
  width: 1920,
  height: 1080,
  safe: { x: 96, y: 204, width: 1728, height: 564 },
};

/** Scale factor that fits the stage into the viewport, letterboxed. */
export function useStageScale(stage: StageGeometry = DEFAULT_STAGE): number {
  const { width, height } = useWindowSize({ initializeWithValue: true });
  if (!width || !height) return 1;
  return Math.min(width / stage.width, height / stage.height);
}
