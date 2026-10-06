import Countdown, { type CountdownRenderProps } from "react-countdown";

import type { Pass } from "../api/client";
import { asLive, type CountdownLive } from "../api/live";
import { UI, primaryLang } from "../lib/i18n";
import { Body, Kicker, Title } from "./common";

export function CountdownSlide({ pass }: { pass: Pass }) {
  const live = asLive<CountdownLive>(pass.live);
  const lang = primaryLang(pass.lang);
  const labels = UI[lang];
  const renderer = ({ days, hours, minutes, seconds, completed }: CountdownRenderProps) => {
    if (completed) {
      return <p className="text-[112px] font-extrabold leading-none">{labels.started}</p>;
    }
    const blocks: Array<[number, string]> = [
      [hours, labels.hours],
      [minutes, labels.minutes],
      [seconds, labels.seconds],
    ];
    if (days > 0) blocks.unshift([days, labels.days]);
    return (
      <div className="flex gap-10" data-testid="countdown">
        {blocks.map(([value, label]) => (
          <div key={label} className="flex flex-col items-center">
            <span className="font-mono text-[160px] font-bold leading-none tabular">
              {String(value).padStart(2, "0")}
            </span>
            <span className="mt-2 text-[32px] font-medium uppercase tracking-[0.12em] text-ink-muted">
              {label}
            </span>
          </div>
        ))}
      </div>
    );
  };
  return (
    <div className="flex h-full flex-col justify-center gap-6 pr-[280px]">
      <Kicker pass={pass} />
      <Title pass={pass} size={80} />
      {live ? <Countdown date={new Date(live.target)} renderer={renderer} /> : null}
      <Body pass={pass} size={40} />
    </div>
  );
}
