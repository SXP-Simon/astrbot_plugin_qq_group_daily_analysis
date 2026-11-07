import { expect, it } from "vitest";
import { mockIncrementalBatches } from "../data/pluginData";

it("增量批次与游标遵守秒级时间契约，详情时间与列表一致", () => {
  const now = Date.now() / 1000;
  const cursor = mockIncrementalBatches.cursor!;
  const timestamps = [
    cursor.last_analyzed_timestamp,
    cursor.last_message_timestamp,
    ...mockIncrementalBatches.batches.map((batch) => batch.timestamp),
  ];
  for (const timestamp of timestamps) {
    expect(timestamp).toBeGreaterThan(now - 2 * 86400);
    expect(timestamp).toBeLessThanOrEqual(now);
  }
  for (const batch of mockIncrementalBatches.batches) {
    expect(Date.parse(batch.created_at_iso!)).toBe(batch.timestamp * 1000);
  }
});
