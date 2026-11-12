import type { Pass } from "../api/client";
import { FitText } from "../components/FitText";
import { joined, ui } from "../lib/i18n";
import { Body, Title } from "./common";
import { QrPanel } from "./QrSlide";

export function CredentialsSlide({ pass }: { pass: Pass }) {
  const wifi = pass.content.wifi_credentials;
  const rows = wifi
    ? [
        { key: "ssid", label: ui("network", pass.lang), value: wifi.ssid },
        ...(wifi.password === null
          ? []
          : [{ key: "password", label: ui("password", pass.lang), value: wifi.password }]),
      ]
    : [];
  const link = pass.content.link;
  return (
    <div className="flex h-full gap-12">
      <div className="flex min-w-0 flex-1 flex-col gap-5 pt-2">
        <Title pass={pass} size={72} />
        <div className="surface flex flex-col gap-3 px-10 py-5">
          {rows.map(({ key, label, value }) => (
            <div key={key} className="flex min-w-0 flex-col">
              <span className="text-[28px] font-medium uppercase tracking-[0.08em] text-ink-muted">{label}</span>
              <FitText max={60} min={24} watch={value} className="max-h-[90px] w-full">
                <span className="block whitespace-pre-wrap break-all font-mono font-semibold leading-tight tabular">
                  <span aria-hidden className="text-ink-dim">"</span>
                  <code data-credential-value={key} className="font-mono text-[1em]">{value}</code>
                  <span aria-hidden className="text-ink-dim">"</span>
                </span>
              </FitText>
            </div>
          ))}
        </div>
        <Body pass={pass} size={38} />
      </div>
      {link?.qr_payload ? <QrPanel value={link.qr_payload} label={joined(link.label, pass.lang)} /> : null}
    </div>
  );
}
