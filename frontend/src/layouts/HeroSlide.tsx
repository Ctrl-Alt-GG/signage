import type { Pass } from "../api/client";
import { Body, Kicker, Title } from "./common";

export function HeroSlide({ pass }: { pass: Pass }) {
  // A stacked pass carries two titles and two bodies, so it gets a smaller scale.
  const stacked = pass.lang === "both";
  const longTitle = (pass.content.title.hu || "").length > 28;
  const titleSize = stacked ? (longTitle ? 80 : 92) : longTitle ? 96 : 112;
  return (
    <div className="flex h-full flex-col justify-center gap-5 pr-[280px]">
      <Kicker pass={pass} />
      <Title pass={pass} size={titleSize} />
      <Body pass={pass} size={stacked ? 40 : 44} />
    </div>
  );
}
