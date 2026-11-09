import { expect, it } from "vitest";
import { mockHandlers } from "@/mocks/handlers";
import { mockCheckpoints } from "@/mocks/data/pluginData";
import { extractData } from "@/shared/api/bridge";
import type { CheckpointsListResponse, CheckpointDetail } from "@/entities/plugin-data/model/types";
it("快照示例支持日期、阶段与任务筛选，分页同值排序稳定", () => {
  const query = {
    group_id: "123456789",
    date_str: "2026-09-26",
    stage_name: "LLM_ANALYSIS",
    trace_id: "trace-20260926-001",
  };
  const filtered = extractData<CheckpointsListResponse>(
    mockHandlers["GET data/checkpoints"](query),
  )!;
  expect(filtered.total).toBe(1);
  expect(filtered.items[0]).toMatchObject(query);
  const first = extractData<CheckpointsListResponse>(
    mockHandlers["GET data/checkpoints"]({ limit: 10 }),
  )!;
  const second = extractData<CheckpointsListResponse>(
    mockHandlers["GET data/checkpoints"]({ limit: 10, offset: 10 }),
  )!;
  expect(first.total).toBeGreaterThan(20);
  expect(
    mockCheckpoints.items.some(
      (item) => item.trace_id?.includes("timeout") && item.stage_name === "RENDER_REPORT",
    ),
  ).toBe(false);
  expect(first.items).toHaveLength(10);
  expect(second.items).toHaveLength(10);
  expect(new Set([...first.items, ...second.items].map((item) => item.checkpoint_id)).size).toBe(
    20,
  );
  expect(first.items.every((item) => item.created_at! < Date.now() / 1000)).toBe(true);
});
it("删除快照同步到列表与详情，不影响同一天其他任务", () => {
  const original = structuredClone(mockCheckpoints);
  const item = original.items[0];
  const locator = {
    kind: "checkpoint",
    group_id: item.group_id,
    date_str: item.date_str,
    stage_name: item.stage_name,
    trace_id: item.trace_id,
  };
  const detail = extractData<CheckpointDetail>(mockHandlers["GET data/checkpoint/detail"](locator));
  try {
    expect(detail?.data).toBeDefined();
    expect(mockHandlers["POST data/checkpoint"](locator).status).toBe("ok");
    expect(mockCheckpoints.items).toHaveLength(original.total - 1);
    expect(mockHandlers["GET data/checkpoint/detail"](locator).status).toBe("error");
  } finally {
    mockHandlers["POST plugin-data/records/mutate"]({ locator, operation: "create", data: detail });
    Object.assign(mockCheckpoints, original);
  }
});

it("快照会话列表与分页记录使用同一任务身份", () => {
  const sessions = mockHandlers["GET data/checkpoints/groups"]().data.sessions;
  expect(sessions.length).toBeGreaterThan(0);
  for (const session of sessions) {
    const result = mockHandlers["GET data/checkpoints"]({
      platform: session.platform,
      group_id: session.group_id,
      limit: 1000,
    }).data;
    expect(result.total).toBeGreaterThan(0);
    expect(
      result.items.every(
        (item) => item.platform === session.platform && item.group_id === session.group_id,
      ),
    ).toBe(true);
  }
});
