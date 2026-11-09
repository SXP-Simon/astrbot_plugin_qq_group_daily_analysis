import { expect, it } from "vitest";
import type { TraceRecord } from "@/entities/trace/model/types";
import { mockHandlers } from "@/mocks/handlers";
import { mockTraces } from "@/mocks/data/traces";

it("演示列表支持分页及四种排序，总数为筛选后、分页前数量", () => {
  const initialOrder = mockTraces.map((trace) => trace.trace_id);
  for (const field of ["started_at", "duration_ms", "total_tokens", "compression_ratio"] as const) {
    for (const direction of ["asc", "desc"]) {
      const all = mockHandlers["GET traces"]({
        sort_by: field,
        sort_order: direction,
        limit: 1000,
      }).data;
      expect(all.items).toHaveLength(all.total);
      const values = all.items
        .map((trace) => trace[field])
        .filter((value): value is number => typeof value === "number");
      expect(values).toEqual([...values].sort((a, b) => (direction === "asc" ? a - b : b - a)));
      const page = mockHandlers["GET traces"]({
        sort_by: field,
        sort_order: direction,
        limit: "2",
        offset: "2",
      }).data;
      expect(page.items.map((trace) => trace.trace_id)).toEqual(
        all.items.slice(2, 4).map((trace) => trace.trace_id),
      );
      expect(page.total).toBe(all.total);
    }
  }
  expect(mockTraces.map((trace) => trace.trace_id)).toEqual(initialOrder);
});

it("群聊精确匹配，搜索覆盖名称与编号，日期和触发条件可以组合", () => {
  const sample = mockTraces[0];
  for (const search of [sample.trace_id, sample.group_id, sample.group_name]) {
    const result = mockHandlers["GET traces"]({ search, limit: 1000 }).data;
    expect(result.items.some((trace) => trace.trace_id === sample.trace_id)).toBe(true);
    expect(
      result.items.every((trace) =>
        [trace.trace_id, trace.group_id, trace.group_name].some((value) =>
          value.toLowerCase().includes(search.toLowerCase()),
        ),
      ),
    ).toBe(true);
  }
  expect(mockHandlers["GET traces"]({ search: "不存在的示例任务" }).data).toEqual({
    items: [],
    total: 0,
    has_more: false,
  });
  const result = mockHandlers["GET traces"]({
    group_id: sample.group_id,
    trigger_type: sample.trigger_type,
    start_time: String(sample.started_at),
    end_time: String(sample.started_at),
  }).data;
  expect(result.items.length).toBeGreaterThan(0);
  expect(
    result.items.every(
      (trace) =>
        trace.group_id === sample.group_id &&
        trace.started_at === sample.started_at &&
        trace.trigger_type === sample.trigger_type,
    ),
  ).toBe(true);
  expect(
    mockHandlers["GET traces"]({ group_id: sample.group_id.slice(0, -1) }).data.items.every(
      (trace) => trace.group_id === sample.group_id.slice(0, -1),
    ),
  ).toBe(true);
});

it("旧成功和取消状态沿用后端别名，未知排序回退开始时间", () => {
  const records: TraceRecord[] = [
    { ...mockTraces[0], trace_id: "mock-filter-completed", status: "completed" },
    { ...mockTraces[0], trace_id: "mock-filter-cancelled", status: "cancelled" },
  ];
  mockTraces.push(...records);
  try {
    expect(
      mockHandlers["GET traces"]({ status: "succeeded", search: "mock-filter" }).data.items.map(
        (trace) => trace.trace_id,
      ),
    ).toEqual(["mock-filter-completed"]);
    expect(
      mockHandlers["GET traces"]({ status: "aborted", search: "mock-filter" }).data.items.map(
        (trace) => trace.trace_id,
      ),
    ).toEqual(["mock-filter-cancelled"]);
    expect(mockHandlers["GET traces"]({ sort_by: "unknown" }).data).toEqual(
      mockHandlers["GET traces"]({ sort_by: "started_at" }).data,
    );
  } finally {
    mockTraces.splice(mockTraces.length - records.length, records.length);
  }
});
it("相同时间的游标继续读取不会因前方新增或删除记录错位", () => {
  const original = [...mockTraces];
  const records = Array.from({ length: 6 }, (_, i) => ({
    ...original[0],
    trace_id: `cursor-${i}`,
    started_at: 100,
  }));
  mockTraces.splice(0, mockTraces.length, ...records);
  try {
    const first = mockHandlers["GET traces"]({ limit: 3 }).data;
    expect(first.has_more).toBe(true);
    const anchor = first.items.at(-1)!;
    mockTraces.splice(4, 1);
    mockTraces.push({ ...records[0], trace_id: "new", started_at: 101 });
    const older = mockHandlers["GET traces"]({
      limit: 3,
      before_time: anchor.started_at,
      before_id: anchor.trace_id,
    }).data;
    expect(older.items.map((item) => item.trace_id)).toEqual(["cursor-2", "cursor-1", "cursor-0"]);
    expect(older.has_more).toBe(false);
  } finally {
    mockTraces.splice(0, mockTraces.length, ...original);
  }
});
