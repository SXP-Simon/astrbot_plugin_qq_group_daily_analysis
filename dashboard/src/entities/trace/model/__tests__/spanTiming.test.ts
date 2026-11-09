import { describe, expect, it } from "vitest";
import { getDurationRatio, getSpanTiming } from "@/entities/trace/model/spanTiming";

describe("阶段耗时与占比", () => {
  it("保留真实零耗时，未知耗时不会变成零或随时钟增长", () => {
    expect(getSpanTiming({ duration_ms: 0, started_at: 1, status: "success" })).toEqual({
      durationMs: 0,
      live: false,
    });
    for (const status of ["success", "failed", "cancelled", "skipped", "running"])
      expect(getSpanTiming({ duration_ms: null, started_at: 1, status }, "failed", 90000)).toEqual({
        durationMs: null,
        live: false,
      });
  });

  it("仅正在执行且有有效开始时间时显示实时耗时", () => {
    expect(
      getSpanTiming({ duration_ms: null, started_at: 10, status: "running" }, "running", 12000),
    ).toEqual({ durationMs: 2000, live: true });
    for (const started_at of [0, NaN, Infinity, 20])
      expect(
        getSpanTiming({ duration_ms: null, started_at, status: "running" }, "running", 12000)
          .durationMs,
      ).toBeNull();
  });

  it("缺失、零和无效分母不制造百分比，也不把比例限制为进度", () => {
    for (const denominator of [undefined, null, 0, -1, Infinity])
      expect(getDurationRatio(10, denominator)).toBeNull();
    expect(getDurationRatio(null, 1000)).toBeNull();
    expect(getDurationRatio(0, 1000)).toBe(0);
    expect(getDurationRatio(3, 1000)).toBe(0.3);
    expect(getDurationRatio(1200, 1000)).toBe(120);
  });

  it("并行子阶段各自相对父阶段计算，不累加或归一化", () => {
    const durations = [800, 700];
    expect(durations.map((value) => getDurationRatio(value, 1000))).toEqual([80, 70]);
  });
});
