import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";

/** True once the web fonts are in, which changes how wide the text is. */
function useFontsReady(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let cancelled = false;
    void document.fonts?.ready.then(() => {
      if (!cancelled) setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return ready;
}

/** Shows its content at the largest font size between `max` and `min` at which it fits
    the box, instead of cutting it off. The box needs a size of its own from its classes:
    a height or a maximum height for text that wraps, a width for a single line.
    Children size themselves in `em`. `watch` names the content, so a new text is fitted
    again. */
export function FitText({
  max,
  min,
  watch,
  className = "",
  children,
}: {
  max: number;
  min: number;
  watch: string;
  className?: string;
  children: ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const fontsReady = useFontsReady();

  useLayoutEffect(() => {
    const element = box.current;
    if (!element) return;
    let size = max;
    element.style.fontSize = `${size}px`;
    // A pixel of slack: fractional line heights round up in scrollHeight.
    while (
      size > min &&
      (element.scrollHeight > element.clientHeight + 1 ||
        element.scrollWidth > element.clientWidth + 1)
    ) {
      size -= 2;
      element.style.fontSize = `${size}px`;
    }
  }, [max, min, watch, fontsReady]);

  return (
    <div ref={box} className={`overflow-hidden ${className}`} data-fit-text>
      {children}
    </div>
  );
}
