import { expect, it } from "vitest";
import { createMockAnalyticsTrends } from "../data/metrics";

it("多渠道示例保留长名称且各范围的次数与消耗和时间桶一致", () => {
  for (const range of [7, 14, 30]) {
    const data = createMockAnalyticsTrends("day", range);
    expect(data.provider_breakdown.length).toBeGreaterThan(7);
    expect(data.provider_breakdown.some((item) => item.name.includes("自定义长名称"))).toBe(true);
    expect(data.provider_breakdown.reduce((sum, item) => sum + item.request_count, 0)).toBe(
      data.points.reduce((sum, point) => sum + point.request_count, 0),
    );
    expect(data.provider_breakdown.reduce((sum, item) => sum + item.total_tokens, 0)).toBe(
      data.points.reduce((sum, point) => sum + point.total_tokens, 0),
    );
  }
});
