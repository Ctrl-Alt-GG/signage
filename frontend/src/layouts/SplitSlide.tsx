import type { Pass } from "../api/client";
import { Text } from "../lib/i18n";
import { Card, Items, Title } from "./common";

export function SplitSlide({ pass }: { pass: Pass }) {
  return (
    <div className="flex h-full flex-col gap-6">
      <div className="pr-[280px]">
        <Title pass={pass} size={72} />
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-2 gap-8">
        {pass.content.columns.slice(0, 2).map((column, index) => (
          <Card key={index} className="min-h-0">
            <Text
              text={column.title}
              lang={pass.lang}
              as="h2"
              className="mb-3 text-[48px] font-bold leading-tight"
              secondaryClassName="text-[0.7em]"
            />
            <Items
              items={column.items.slice(0, 4)}
              lang={pass.lang}
              size={38}
              availableHeight={260}
              columnWidth={760}
              className="justify-start"
            />
          </Card>
        ))}
      </div>
    </div>
  );
}
