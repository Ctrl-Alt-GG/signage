import { useState } from "react";
import { useInterval } from "usehooks-ts";

export function Clock({ timeZone, lang }: { timeZone: string; lang: "hu" | "en" }) {
  const format = () =>
    new Intl.DateTimeFormat(lang === "hu" ? "hu-HU" : "en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone,
    }).format(new Date());
  const [value, setValue] = useState(format);
  useInterval(() => setValue(format()), 1000);
  return (
    <div className="font-mono text-[44px] leading-none text-ink-muted tabular" data-testid="clock">
      {value}
    </div>
  );
}
