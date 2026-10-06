import type { ReactNode } from "react";

import { SAFE, STAGE, useStageScale } from "../lib/stage";

export function Stage({ backgroundUrl, children }: { backgroundUrl: string; children: ReactNode }) {
  const scale = useStageScale();
  return (
    <div className="fixed inset-0 bg-field">
      <div
        className="absolute left-1/2 top-1/2 overflow-hidden bg-field bg-cover bg-center"
        style={{
          width: STAGE.width,
          height: STAGE.height,
          transform: `translate(-50%, -50%) scale(${scale})`,
          backgroundImage: `url("${backgroundUrl}")`,
        }}
        data-stage
      >
        <main
          className="absolute"
          style={{ left: SAFE.x, top: SAFE.y, width: SAFE.width, height: SAFE.height }}
          data-safe-area
        >
          {children}
        </main>
      </div>
    </div>
  );
}
