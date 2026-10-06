import { QRCodeSVG } from "qrcode.react";

import type { Pass } from "../api/client";
import { joined } from "../lib/i18n";
import { Footer, Items, Kicker, Title } from "./common";

export function QrPanel({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex w-[420px] shrink-0 flex-col items-center gap-4 self-center">
      <div className="flex size-[420px] items-center justify-center rounded-[24px] bg-white p-[30px]">
        <QRCodeSVG value={value} size={360} level="M" bgColor="#ffffff" fgColor="#130404" marginSize={0} />
      </div>
      {label ? <p className="text-center text-[30px] font-medium leading-tight text-ink-muted">{label}</p> : null}
    </div>
  );
}

export function QrSlide({ pass }: { pass: Pass }) {
  const link = pass.content.link;
  return (
    <div className="flex h-full gap-12">
      <div className="flex min-w-0 flex-1 flex-col gap-6 pt-6">
        <Kicker pass={pass} />
        <Title pass={pass} size={72} />
        <div className="min-h-0 flex-1">
          <Items items={pass.content.items} lang={pass.lang} size={38} availableHeight={290} columnWidth={1200} />
        </div>
        <Footer pass={pass} />
      </div>
      {link?.qr_payload ? <QrPanel value={link.qr_payload} label={joined(link.label, pass.lang) || link.url} /> : null}
    </div>
  );
}
