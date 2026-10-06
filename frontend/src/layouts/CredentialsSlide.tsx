import type { Bilingual, Lang, Pass } from "../api/client";
import { joined, pick, primaryLang } from "../lib/i18n";
import { Body, Title } from "./common";
import { QrPanel } from "./QrSlide";

interface Credential {
  label: string;
  value: string;
}

function split(text: string): Array<[string, string]> {
  return text
    .split(/\s{2,}/)
    .filter(Boolean)
    .map((line) => {
      const colon = line.indexOf(":");
      return colon < 0 ? ["", line.trim()] : [line.slice(0, colon).trim(), line.slice(colon + 1).trim()];
    });
}

/** The footer carries "Hálózat: SSID  Jelszó: ..." in both languages, resolved by the
    backend. Each credential becomes a small label over a large mono value; on a stacked pass
    the label reads "Hálózat · Network" because the values are the same in both languages. */
function credentials(footer: Bilingual | null | undefined, lang: Pass["lang"]): Credential[] {
  if (!footer) return [];
  if (lang !== "both") {
    return split(pick(footer, primaryLang(lang))).map(([label, value]) => ({ label, value }));
  }
  const hu = split(footer.hu);
  const en = split(footer.en || footer.hu);
  const aligned = hu.length === en.length && hu.every(([, value], i) => en[i]?.[1] === value);
  if (!aligned) {
    const perLang = (lines: Array<[string, string]>, l: Lang) =>
      lines.map(([label, value]) => ({ label: `${label} (${l})`, value }));
    return [...perLang(hu, "hu"), ...perLang(en, "en")];
  }
  return hu.map(([label, value], i) => {
    const enLabel = en[i]?.[0] ?? "";
    const both = label && enLabel && enLabel !== label ? `${label} · ${enLabel}` : label || enLabel;
    return { label: both, value };
  });
}

export function CredentialsSlide({ pass }: { pass: Pass }) {
  const rows = credentials(pass.content.footer, pass.lang);
  const link = pass.content.link;
  return (
    <div className="flex h-full gap-12">
      <div className="flex min-w-0 flex-1 flex-col gap-5 pt-2">
        <Title pass={pass} size={72} />
        <div className="surface flex flex-col gap-3 px-10 py-5">
          {rows.map(({ label, value }) => (
            <div key={`${label}:${value}`} className="flex min-w-0 flex-col">
              {label ? (
                <span className="text-[28px] font-medium uppercase tracking-[0.08em] text-ink-muted">{label}</span>
              ) : null}
              <span className="truncate font-mono text-[60px] font-semibold leading-tight tabular" data-allow-clip>
                {value}
              </span>
            </div>
          ))}
        </div>
        <Body pass={pass} size={38} />
      </div>
      {link?.qr_payload ? <QrPanel value={link.qr_payload} label={joined(link.label, pass.lang)} /> : null}
    </div>
  );
}
