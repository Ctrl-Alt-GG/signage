import { useEffect, useRef, useState } from "react";
import useEmblaCarousel from "embla-carousel-react";
import Autoplay from "embla-carousel-autoplay";
import Fade from "embla-carousel-fade";

import type { Pass } from "../api/client";
import { Progress } from "./Chrome";
import { SlidePass } from "./SlidePass";

/** Rotates the passes with Embla: autoplay with a per-pass delay and a crossfade. When the
    bundle changes, the carousel re-initialises and resumes on the pass that was showing. */
export function Rotation({
  passes,
  showProgress,
  frozen,
  onPassChange,
}: {
  passes: Pass[];
  showProgress: boolean;
  frozen: boolean;
  onPassChange: (pass: Pass) => void;
}) {
  const delays = passes.map((pass) => pass.duration_ms);
  const [emblaRef, embla] = useEmblaCarousel(
    { loop: passes.length > 1, duration: 24, watchDrag: false, containScroll: false },
    [
      Autoplay({
        delay: () => delays,
        stopOnInteraction: false,
        stopOnMouseEnter: false,
        playOnInit: !frozen,
      }),
      Fade(),
    ],
  );
  const [index, setIndex] = useState(0);
  const lastKey = useRef<string | null>(null);

  useEffect(() => {
    if (!embla) return;
    const select = () => {
      const current = embla.selectedScrollSnap();
      setIndex(current);
      const pass = passes[current];
      if (pass) {
        lastKey.current = pass.key;
        onPassChange(pass);
      }
    };
    const reinit = () => {
      const wanted = passes.findIndex((pass) => pass.key === lastKey.current);
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
  }, [embla, passes, onPassChange]);

  useEffect(() => {
    const autoplay = embla?.plugins().autoplay;
    if (!autoplay) return;
    if (frozen || passes.length <= 1) autoplay.stop();
    else autoplay.play();
  }, [embla, frozen, passes.length]);

  const current = passes[index];
  return (
    <div className="relative h-full w-full">
      <div className="embla h-full w-full overflow-hidden" ref={emblaRef}>
        <div className="embla__container embla__fade flex h-full">
          {passes.map((pass) => (
            <div className="embla__slide h-full min-w-0 flex-[0_0_100%]" key={pass.key}>
              <SlidePass pass={pass} />
            </div>
          ))}
        </div>
      </div>
      {showProgress && current && !frozen && passes.length > 1 ? (
        <Progress durationMs={current.duration_ms} passKey={current.key} />
      ) : null}
    </div>
  );
}
