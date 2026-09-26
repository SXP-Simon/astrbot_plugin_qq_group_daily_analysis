import { describe, it, expect } from "vitest";
import { formatBytes, formatCost, formatDuration, formatPercent, formatTokens } from "../formatters";

describe("数据格式化工具库 (Shared Formatters Library)", () => {
  describe("formatBytes (字节换算)", () => {
    it("能够将字节正确换算为 KB, MB, GB 单位字符串", () => {
      expect(formatBytes(0)).toBe("0 B");
      expect(formatBytes(1024)).toBe("1.0 KB");
      expect(formatBytes(1048576)).toBe("1.0 MB");
      expect(formatBytes(1073741824)).toBe("1.0 GB");
    });

    it("能够安全容错处理负数与 NaN 非法数值", () => {
      expect(formatBytes(-10)).toBe("0 B");
      expect(formatBytes(NaN)).toBe("0 B");
    });
  });

  describe("formatDuration (耗时格式化)", () => {
    it("能够精确将毫秒数值转换为对应的时间描述", () => {
      expect(formatDuration(500)).toBe("500ms");
      expect(formatDuration(1500)).toBe("1.50s");
      expect(formatDuration(65000)).toBe("65.00s");
    });

    it("当耗时为 0 或 undefined 时展示默认占位符", () => {
      expect(formatDuration(0)).toBe("-");
      expect(formatDuration(undefined)).toBe("-");
    });
  });

  describe("formatPercent (百分比格式化)", () => {
    it("能够正确将浮点数格式化为百分比", () => {
      expect(formatPercent(0.95456)).toBe("95%");
      expect(formatPercent(0)).toBe("0%");
      expect(formatPercent(undefined)).toBe("-");
    });
  });

  describe("formatTokens 与 formatCost (模型消耗格式化)", () => {
    it("能够格式化 Token 计数并千分位展示，保留费用浮点数精度", () => {
      expect(formatTokens(12345)).toBe("12,345");
      expect(formatTokens(undefined)).toBe("-");
      expect(formatCost(0.0521)).toBe("$0.0521");
      expect(formatCost(undefined)).toBe("$0.00");
    });
  });
});
