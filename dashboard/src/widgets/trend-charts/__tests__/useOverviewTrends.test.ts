import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchAnalyticsTrends } from "../../../entities/metric/api/metricApi";
import type { AnalyticsTrendsResponse } from "../../../entities/metric/model/types";
import { createMockAnalyticsTrends } from "../../../mocks/data/metrics";
import { useOverviewTrends } from "../model/useOverviewTrends";

vi.mock("../../../entities/metric/api/metricApi", () => ({ fetchAnalyticsTrends: vi.fn() }));
const initial = createMockAnalyticsTrends();
function deferred() {
  let resolve!: (value: AnalyticsTrendsResponse | null) => void;
  const promise = new Promise<AnalyticsTrendsResponse | null>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchAnalyticsTrends).mockImplementation(async (granularity, count) =>
    createMockAnalyticsTrends(granularity, count),
  );
});

describe("趋势范围与请求状态", () => {
  it("有效默认快照直接展示，缺失或范围不符则读取十四天", async () => {
    const first = renderHook(() => useOverviewTrends(initial));
    expect(first.result.current.points).toEqual(initial.points);
    expect(fetchAnalyticsTrends).not.toHaveBeenCalled();
    first.unmount();
    const mismatched = createMockAnalyticsTrends("day", 7);
    const next = renderHook(() => useOverviewTrends(mismatched));
    await waitFor(() => expect(next.result.current.loading).toBe(false));
    expect(fetchAnalyticsTrends).toHaveBeenCalledWith("day", 14);
    expect(next.result.current.displayedRange).toBe("14d");
  });

  it("快速切换以最后一次为准；旧响应不能覆盖新范围或提前结束加载", async () => {
    const weekly = deferred();
    const hourly = deferred();
    vi.mocked(fetchAnalyticsTrends)
      .mockReturnValueOnce(weekly.promise)
      .mockReturnValueOnce(hourly.promise);
    const { result } = renderHook(() => useOverviewTrends(initial));
    act(() => result.current.selectRange("7d"));
    act(() => result.current.selectRange("48h"));
    expect(fetchAnalyticsTrends).toHaveBeenNthCalledWith(1, "day", 7);
    expect(fetchAnalyticsTrends).toHaveBeenNthCalledWith(2, "hour", 48);
    await act(async () => weekly.resolve(createMockAnalyticsTrends("day", 7)));
    expect(result.current.loading).toBe(true);
    expect(result.current.displayedRange).toBe("14d");
    await act(async () => hourly.resolve(createMockAnalyticsTrends("hour", 48)));
    expect(result.current.displayedRange).toBe("48h");
    expect(result.current.points).toHaveLength(48);
    expect(result.current.loading).toBe(false);
  });

  it("失败保留明确属于旧范围的数据，重试成功再切换", async () => {
    vi.mocked(fetchAnalyticsTrends).mockRejectedValueOnce(new Error("离线"));
    const { result } = renderHook(() => useOverviewTrends(initial));
    act(() => result.current.selectRange("30d"));
    await waitFor(() => expect(result.current.error).toContain("检查连接"));
    expect(result.current.range).toBe("30d");
    expect(result.current.displayedRange).toBe("14d");
    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.displayedRange).toBe("30d"));
    expect(result.current.error).toBe("");
    expect(result.current.points).toHaveLength(30);
  });

  it.each([
    null,
    { ...initial, range_count: 7 },
    { ...initial, points: [{ ...initial.points[0], total_tokens: -1 }] },
  ])("无效响应不替换已有结果", async (response) => {
    vi.mocked(fetchAnalyticsTrends).mockResolvedValueOnce(response);
    const { result } = renderHook(() => useOverviewTrends(initial));
    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.error).toContain("不完整或时间范围不符"));
    expect(result.current.points).toEqual(initial.points);
  });

  it("非默认范围不被新的总览快照重置，卸载后迟到结果失效", async () => {
    const request = deferred();
    vi.mocked(fetchAnalyticsTrends).mockReturnValueOnce(request.promise);
    const { result, rerender, unmount } = renderHook(({ seed }) => useOverviewTrends(seed), {
      initialProps: { seed: initial },
    });
    act(() => result.current.selectRange("7d"));
    rerender({ seed: { ...initial, points: [] } });
    expect(fetchAnalyticsTrends).toHaveBeenCalledOnce();
    unmount();
    await act(async () => request.resolve(createMockAnalyticsTrends("day", 7)));
    expect(result.current.displayedRange).toBe("14d");
  });

  it("零消耗按零计算，超过七个服务商聚合显示但保留完整明细", () => {
    const data = {
      ...initial,
      points: initial.points.map((point) => ({
        ...point,
        request_count: 0,
        total_tokens: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
      })),
      provider_breakdown: Array.from({ length: 9 }, (_, index) => ({
        name: `示例渠道 ${index}`,
        total_tokens: index * 10,
        request_count: 1,
      })),
    };
    const { result } = renderHook(() => useOverviewTrends(data));
    expect(result.current.totalRequests).toBe(0);
    expect(result.current.totalTokens).toBe(0);
    expect(result.current.providers).toHaveLength(9);
    expect(result.current.providerChart).toHaveLength(7);
    expect(result.current.providerChart.at(-1)).toMatchObject({
      name: "其他服务商（3个）",
      total_tokens: 30,
      request_count: 3,
    });
    expect(data.provider_breakdown[0].name).toBe("示例渠道 0");
  });
});
