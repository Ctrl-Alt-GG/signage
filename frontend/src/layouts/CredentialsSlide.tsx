import type { Pass } from "../api/client";
import { pick, primaryLang } from "../lib/i18n";
import { Body, Title } from "./common";
import { QrPanel } from "./QrSlide";

/** Footer carries "Hálózat: SSID  Jelszó: ..." resolved by the backend; split it back into
    two mono lines so the room can read the password from the back row. */
export function CredentialsSlide({ pass }: { pass: Pass }) {
  const lang = primaryLang(pass.lang);
  const footer = pick(pass.content.footer, lang);
  const lines = footer.split(/\s{2,}/).filter(Boolean);
  const link = pass.content.link;
  return (
    <div className="flex h-full gap-12">
      <div className="flex min-w-0 flex-1 flex-col gap-8 pt-4">
        <Title pass={pass} size={72} />
        <div className="surface flex flex-col gap-4 px-10 py-8 font-mono text-[64px] font-semibold leading-tight tabular">
          {lines.map((line) => (
            <span key={line} className="truncate">
              {line}
            </span>
          ))}
        </div>
        <Body pass={pass} size={44} />
      </div>
      {link?.qr_payload ? <QrPanel value={link.qr_payload} label={pick(link.label, lang)} /> : null}
    </div>
  );
}
