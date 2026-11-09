import { expect, it } from "vitest";
import { mockHandlers } from "@/mocks/handlers";
import { extractData } from "@/shared/api/bridge";
import type {
  IncrementalBatchItem,
  IncrementalBatchesResponse,
} from "@/entities/plugin-data/model/types";
import { mockIncrementalBatches } from "@/mocks/data/pluginData";

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

it("切换群和批次返回对应数据，不再总是返回第一份批次", () => {
  const other = extractData<IncrementalBatchesResponse>(
    mockHandlers["GET data/incremental/batches"]({ platform_id: "aiocqhttp", group_id: "其他群" }),
  );
  expect(other?.batches).toEqual([]);
  expect(other?.cursor).toMatchObject({
    group_id: "其他群",
    last_analyzed_timestamp: 0,
  });
  for (const batch of mockIncrementalBatches.batches) {
    const detail = extractData<IncrementalBatchItem>(
      mockHandlers["GET data/incremental/batch/detail"]({
        platform_id: "aiocqhttp",
        group_id: batch.group_id,
        batch_id: batch.batch_id,
      }),
    );
    expect(detail?.batch_id).toBe(batch.batch_id);
    expect(detail?.topics).toEqual(batch.topics);
  }
  expect(
    mockHandlers["GET data/incremental/batch/detail"]({
      group_id: "其他群",
      batch_id: mockIncrementalBatches.batches[0].batch_id,
    }).status,
  ).toBe("error");
});

it("单批删除和整群重置同步到列表、详情及游标", () => {
  const original = structuredClone(mockIncrementalBatches);
  try {
    const first = original.batches[0];
    expect(
      mockHandlers["POST data/incremental/batch"]({
        platform_id: "aiocqhttp",
        group_id: first.group_id,
        batch_id: first.batch_id,
      }).status,
    ).toBe("ok");
    expect(
      mockHandlers["GET data/incremental/batch/detail"]({
        platform_id: "aiocqhttp",
        group_id: first.group_id,
        batch_id: first.batch_id,
      }).status,
    ).toBe("error");
    expect(mockIncrementalBatches.batches.some((batch) => batch.batch_id === first.batch_id)).toBe(
      false,
    );
    const remaining = mockIncrementalBatches.batches.length;
    expect(
      mockHandlers["POST data/incremental/reset"]({
        platform_id: "aiocqhttp",
        group_id: first.group_id,
      }).data,
    ).toMatchObject({ deleted_batches: remaining });
    expect(mockIncrementalBatches.batches).toHaveLength(0);
    expect(mockIncrementalBatches.cursor.last_analyzed_timestamp).toBe(0);
  } finally {
    for (const batch of original.batches) {
      mockHandlers["POST plugin-data/records/mutate"]({
        locator: {
          kind: "batch",
          platform_id: "aiocqhttp",
          group_id: batch.group_id,
          batch_id: batch.batch_id,
        },
        operation: "create",
        data: batch,
      });
    }
    Object.assign(mockIncrementalBatches, original);
  }
});

it("多页示例按时间倒序，分页条目不重复且页码越界会修正", () => {
  const get = (page: number) =>
    extractData<IncrementalBatchesResponse>(
      mockHandlers["GET data/incremental/batches"]({
        platform_id: "aiocqhttp",
        group_id: "123456789",
        page,
        page_size: 20,
      }),
    )!;
  const first = get(1),
    last = get(99);
  expect(first.total).toBeGreaterThan(20);
  expect(first.batches).toHaveLength(20);
  expect(last.page).toBe(2);
  expect(new Set([...first.batches, ...last.batches].map((item) => item.batch_id)).size).toBe(
    first.total,
  );
  for (const batch of [...first.batches, ...last.batches]) {
    for (const topic of batch.topics ?? []) {
      expect(topic.topic).toBeTruthy();
      expect(topic).not.toHaveProperty("heat_score");
    }
  }
});

it("增量群聊目录分开同号平台，另一平台重置不会删除现有批次", () => {
  const directory = mockHandlers["GET data/incremental/groups"]().data;
  const details = directory.group_details.filter((group) => group.group_id === "123456789");
  expect(details.map((group) => group.platform_id).sort()).toEqual(["aiocqhttp", "telegram"]);
  expect(details.find((group) => group.platform_id === "telegram")?.group_name).toBe(
    "摄影交流示例群",
  );
  const before = mockIncrementalBatches.batches.length;
  expect(
    mockHandlers["POST data/incremental/reset"]({ group_id: "123456789", platform_id: "telegram" })
      .data,
  ).toMatchObject({ deleted_batches: 0 });
  expect(mockIncrementalBatches.batches).toHaveLength(before);
  expect(
    mockHandlers["GET data/incremental/batches"]({ group_id: "123456789", platform_id: "telegram" })
      .data?.batches,
  ).toEqual([]);
});
