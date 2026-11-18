import Countdown, { type CountdownRenderProps } from "react-countdown";

import type { LiveClockPass } from "../api/client";
import { serverNow } from "../lib/clock";
import { UI, ui } from "../lib/i18n";
import { Body, Kicker, Title } from "./common";

export function CountdownSlide({ pass }: { pass: LiveClockPass }) {
  const live = pass.live;
  const renderer = ({ days, hours, minutes, seconds, completed }: CountdownRenderProps) => {
    if (completed) {
      return pass.lang === "both" ? (
        <p className="text-[112px] font-extrabold leading-none">
          <span className="block">{UI.hu.started}</span>
          <span className="block text-[0.72em] text-ink-muted">{UI.en.started}</span>
        </p>
      ) : (
        <p className="text-[112px] font-extrabold leading-none">{ui("started", pass.lang)}</p>
      );
    }
    const blocks: Array<[number, string]> = [
      [hours, ui("hours", pass.lang)],
      [minutes, ui("minutes", pass.lang)],
      [seconds, ui("seconds", pass.lang)],
    ];
    if (days > 0) blocks.unshift([days, ui("days", pass.lang)]);
    return (
      <div className="flex gap-10" data-testid="countdown">
        {blocks.map(([value, label]) => (
          <div key={label} className="flex flex-col items-center">
            <span className="font-mono text-[144px] font-bold leading-none tabular">
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
    <div className="flex h-full flex-col justify-center gap-5 pr-[280px]">
      <Kicker pass={pass} />
      <Title pass={pass} size={80} />
      {/* Counted against the server's clock: the kiosk's own may be minutes off. */}
      {live ? <Countdown date={new Date(live.target)} now={serverNow} renderer={renderer} /> : null}
      <Body pass={pass} size={40} />
    </div>
  );
}
