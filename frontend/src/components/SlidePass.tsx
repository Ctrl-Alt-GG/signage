import type { Pass } from "../api/client";
import { CountdownSlide } from "../layouts/CountdownSlide";
import { CredentialsSlide } from "../layouts/CredentialsSlide";
import { HeroSlide } from "../layouts/HeroSlide";
import { ListSlide } from "../layouts/ListSlide";
import { NowNextSlide } from "../layouts/NowNextSlide";
import { QrSlide } from "../layouts/QrSlide";
import { ScheduleSlide } from "../layouts/ScheduleSlide";
import { ServersSlide } from "../layouts/ServersSlide";
import { SplitSlide } from "../layouts/SplitSlide";
import { StreamsSlide } from "../layouts/StreamsSlide";
import { TournamentSlide } from "../layouts/TournamentSlide";

const TEXT_LAYOUTS = {
  hero: HeroSlide,
  list: ListSlide,
  split: SplitSlide,
  qr: QrSlide,
  credentials: CredentialsSlide,
} as const;

/** The live data of a pass is that of its source, so the source picks the layout, among
    the ones its data suits when there are several. */
function Layout({ pass }: { pass: Pass }) {
  switch (pass.source) {
    case "static": {
      const Text = TEXT_LAYOUTS[pass.layout] ?? HeroSlide;
      return <Text pass={pass} />;
    }
    case "live:clock":
      return <CountdownSlide pass={pass} />;
    case "live:schedule":
      return pass.layout === "schedule" ? <ScheduleSlide pass={pass} /> : <NowNextSlide pass={pass} />;
    case "live:projectile":
      return <ServersSlide pass={pass} />;
    case "live:bracket":
      return <TournamentSlide pass={pass} />;
    case "live:streams":
      return <StreamsSlide pass={pass} />;
    default:
      // A source from a newer server than this page: its text, at least.
      return <HeroSlide pass={pass} />;
  }
}

export function SlidePass({ pass }: { pass: Pass }) {
  return (
    <section
      className="relative h-full w-full px-12 py-10"
      data-slide={pass.slide}
      data-layout={pass.layout}
      data-lang={pass.lang}
    >
      <Layout pass={pass} />
    </section>
  );
}
