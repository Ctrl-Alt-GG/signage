import type { Pass } from "../api/client";
import { joined } from "../lib/i18n";
import { Card, Items, Title } from "./common";

export function SplitSlide({ pass }: { pass: Pass }) {
  return (
    <div className="flex h-full flex-col gap-6">
      <div className="pr-[280px]">
        <Title pass={pass} size={64} />
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-2 gap-8">
        {pass.content.columns.slice(0, 2).map((column, index) => (
          <Card key={index} className="min-h-0 overflow-hidden">
            <h2 className="mb-3 text-[44px] font-bold leading-tight">{joined(column.title, pass.lang)}</h2>
            <Items
              items={column.items.slice(0, 4)}
              lang={pass.lang}
              size={36}
              availableHeight={250}
              columnWidth={740}
              className="justify-start"
            />
          </Card>
        ))}
      </div>
    </div>
  );
}
