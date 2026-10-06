import type { ReactNode } from "react";

import { DEFAULT_STAGE, type StageGeometry, useStageScale } from "../lib/stage";

export function Stage({
  backgroundUrl,
  stage,
  children,
}: {
  backgroundUrl: string;
  stage?: StageGeometry | null;
  children: ReactNode;
}) {
  const geometry = stage ?? DEFAULT_STAGE;
  const scale = useStageScale(geometry);
  return (
    <div className="fixed inset-0 bg-field">
      <div
        className="absolute left-1/2 top-1/2 overflow-hidden bg-field bg-cover bg-center"
        style={{
          width: geometry.width,
          height: geometry.height,
          transform: `translate(-50%, -50%) scale(${scale})`,
          backgroundImage: `url("${backgroundUrl}")`,
        }}
        data-stage
      >
        <main
          className="absolute"
          style={{
            left: geometry.safe.x,
            top: geometry.safe.y,
            width: geometry.safe.width,
            height: geometry.safe.height,
          }}
          data-safe-area
        >
          {children}
        </main>
      </div>
    </div>
  );
}
