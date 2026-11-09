import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { IncrementalCursorCards } from "@/pages/plugin-data/ui/incremental/IncrementalCursorCards";
afterEach(cleanup);
it("初始游标不伪造时间，零批次与零去重数仍明确显示", () => {
  render(
    <IncrementalCursorCards
      cursor={{
        group_id: "a",
        last_analyzed_timestamp: 0,
        last_message_timestamp: 0,
        tracked_message_ids_count: 0,
      }}
      batchCount={0}
    />,
  );
  expect(screen.getByText("尚未分析")).toBeVisible();
  expect(screen.getByText("未记录")).toBeVisible();
  expect(screen.getByText("0 条")).toBeVisible();
  expect(screen.getByText("0 个")).toBeVisible();
});
