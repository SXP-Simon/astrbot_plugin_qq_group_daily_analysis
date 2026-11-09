import { describe, expect, it } from "vitest";
import { mockHandlers } from "@/mocks/handlers";
import { mockMetricsSummary } from "@/mocks/data/metrics";

describe("趋势示例接口", () => {
  it.each([
    ["hour", 48],
    ["day", 7],
    ["day", 14],
    ["day", 30],
  ])("按 %s / %s 分桶并保持消耗、次数和分布一致", (granularity, range_count) => {
    const data = mockHandlers["GET metrics/trends"]({ granularity, range_count }).data;
    expect(data.granularity).toBe(granularity);
    expect(data.range_count).toBe(range_count);
    expect(data.points).toHaveLength(Number(range_count));
    const tokens = data.points.reduce((sum, point) => sum + point.total_tokens, 0);
    const requests = data.points.reduce((sum, point) => sum + point.request_count, 0);
    expect(data.provider_breakdown.reduce((sum, item) => sum + item.total_tokens, 0)).toBe(tokens);
    expect(data.model_breakdown.reduce((sum, item) => sum + item.request_count, 0)).toBe(requests);
    for (let i = 0; i < data.points.length; i += 1) {
      const point = data.points[i];
      expect(point.total_tokens).toBe(point.prompt_tokens + point.completion_tokens);
      expect(point.request_count).toBe(point.succeeded_count + point.failed_count);
      if (i)
        expect(point.timestamp - data.points[i - 1].timestamp).toBe(
          granularity === "hour" ? 3600 : 86400,
        );
    }
  });
  it("默认十四天和总览一致，七天是三十天的尾段，空时段仍保留零", () => {
    const monthly = mockHandlers["GET metrics/trends"]({ range_count: 30 }).data;
    const weekly = mockHandlers["GET metrics/trends"]({ range_count: 7 }).data;
    expect(weekly.points).toEqual(monthly.points.slice(-7));
    expect(mockHandlers["GET metrics/trends"]().data).toEqual(mockMetricsSummary.trends);
    expect(monthly.points.some((point) => point.request_count === 0)).toBe(true);
    expect(monthly.points.reduce((sum, point) => sum + point.request_count, 0)).toBe(
      mockMetricsSummary.total_traces,
    );
    expect(monthly.points.reduce((sum, point) => sum + point.total_tokens, 0)).toBe(
      mockMetricsSummary.total_tokens_spent,
    );
    expect(monthly.points.at(-1)?.total_tokens).toBe(mockMetricsSummary.today_tokens_spent);
  });
  it("限制无效或过大的范围，不生成无限示例数据", () => {
    expect(mockHandlers["GET metrics/trends"]({ range_count: "oops" }).data.points).toHaveLength(
      14,
    );
    expect(mockHandlers["GET metrics/trends"]({ range_count: -1 }).data.points).toHaveLength(1);
    expect(
      mockHandlers["GET metrics/trends"]({ granularity: "hour", range_count: 999 }).data.points,
    ).toHaveLength(168);
  });
});
