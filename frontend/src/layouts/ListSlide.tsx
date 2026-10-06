import type { Pass } from "../api/client";
import { Footer, Items, Kicker, Title } from "./common";

export function ListSlide({ pass }: { pass: Pass }) {
  return (
    <div className="flex h-full gap-12">
      <div className="flex w-[560px] shrink-0 flex-col gap-4 pt-6">
        <Kicker pass={pass} />
        <Title pass={pass} size={72} />
        <Footer pass={pass} />
      </div>
      <div className="min-w-0 flex-1 pt-6">
        <Items items={pass.content.items} lang={pass.lang} availableHeight={440} columnWidth={1000} />
      </div>
    </div>
  );
}
