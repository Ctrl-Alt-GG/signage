import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import useEmblaCarousel from "embla-carousel-react";
import Fade from "embla-carousel-fade";
import { ErrorBoundary } from "react-error-boundary";

import type { Pass } from "../api/client";
import { Progress } from "./Chrome";
import { SlidePass } from "./SlidePass";

/** Rotates the passes with Embla and a crossfade. Each pass is shown for its own
    duration, which is read when the pass comes up: a duration edited in the admin applies
    the next time round, and a pass added later is timed like any other. When the bundle
    changes, the carousel re-initialises and resumes on the pass that was showing.

    A pass that fails to render is left out of the rotation instead of taking the screen
    down, and is tried again when its data changes. */
export function Rotation({
  passes,
  showProgress,
  frozen,
  empty,
  onPassChange,
}: {
  passes: Pass[];
  showProgress: boolean;
  frozen: boolean;
  /** Shown when no pass is left to show. */
  empty: ReactNode;
  onPassChange: (pass: Pass) => void;
}) {
  // The pass as it was when it failed. The same key with other data is another try.
  const [failed, setFailed] = useState<ReadonlyMap<string, Pass>>(new Map());
  const shown = useMemo(
    () => passes.filter((pass) => failed.get(pass.key) !== pass),
    [passes, failed],
  );

  const [emblaRef, embla] = useEmblaCarousel(
    { loop: shown.length > 1, duration: 24, watchDrag: false, containScroll: false },
    [Fade()],
  );
  const [index, setIndex] = useState(0);
  const lastKey = useRef<string | null>(null);

  useEffect(() => {
    if (!embla) return;
    const select = () => {
      const current = embla.selectedScrollSnap();
      setIndex(current);
      const pass = shown[current];
      if (pass) {
        lastKey.current = pass.key;
        onPassChange(pass);
      }
    };
    const reinit = () => {
      const wanted = shown.findIndex((pass) => pass.key === lastKey.current);
      if (wanted >= 0 && wanted !== embla.selectedScrollSnap()) embla.scrollTo(wanted, true);
      select();
    };
    embla.on("select", select);
    embla.on("reInit", reinit);
    select();
    return () => {
      embla.off("select", select);
      embla.off("reInit", reinit);
    };
  }, [embla, shown, onPassChange]);

  const current = shown[index];
  const currentKey = current?.key;
  const duration = current?.duration_ms;
  const rotates = !frozen && shown.length > 1;

  // The timer belongs to the pass that is showing. It depends on the key and the duration,
  // not on the pass object, so the poll that brings the same pass again every few seconds
  // does not start it over, which would keep a long slide on the screen for ever.
  useEffect(() => {
    if (!embla || !rotates || currentKey === undefined || duration === undefined) return;
    const timer = window.setTimeout(() => embla.scrollNext(), duration);
    return () => window.clearTimeout(timer);
  }, [embla, rotates, currentKey, duration]);

  if (shown.length === 0) return <>{empty}</>;

  return (
    <div className="relative h-full w-full">
      <div className="embla h-full w-full overflow-hidden" ref={emblaRef}>
        <div className="embla__container embla__fade flex h-full">
          {shown.map((pass) => (
            <div className="embla__slide h-full min-w-0 flex-[0_0_100%]" key={pass.key}>
              <ErrorBoundary
                fallback={null}
                onError={(error) => {
                  console.error(`slide ${pass.key} could not be shown and is skipped`, error);
                  setFailed((before) => new Map(before).set(pass.key, pass));
                }}
              >
                <SlidePass pass={pass} />
              </ErrorBoundary>
            </div>
          ))}
        </div>
      </div>
      {showProgress && current && rotates ? (
        <Progress durationMs={current.duration_ms} passKey={current.key} />
      ) : null}
    </div>
  );
}
