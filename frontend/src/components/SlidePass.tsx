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

const LAYOUTS = {
  hero: HeroSlide,
  list: ListSlide,
  split: SplitSlide,
  qr: QrSlide,
  credentials: CredentialsSlide,
  now_next: NowNextSlide,
  schedule: ScheduleSlide,
  servers: ServersSlide,
  tournament: TournamentSlide,
  streams: StreamsSlide,
  countdown: CountdownSlide,
} as const;

export function SlidePass({ pass }: { pass: Pass }) {
  const Layout = LAYOUTS[pass.layout as keyof typeof LAYOUTS] ?? HeroSlide;
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
