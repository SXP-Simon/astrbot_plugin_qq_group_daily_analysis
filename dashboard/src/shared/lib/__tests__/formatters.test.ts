import { describe, it, expect } from "vitest";
import { formatBytes, formatCost, formatDuration, formatPercent, formatTokens } from "../formatters";

describe("Shared Formatters Library", () => {
  describe("formatBytes", () => {
    it("should format bytes correctly into KB, MB, GB", () => {
      expect(formatBytes(0)).toBe("0 B");
      expect(formatBytes(1024)).toBe("1.0 KB");
      expect(formatBytes(1048576)).toBe("1.0 MB");
      expect(formatBytes(1073741824)).toBe("1.0 GB");
    });

    it("should handle nullish or negative numbers gracefully", () => {
      expect(formatBytes(-10)).toBe("0 B");
      expect(formatBytes(NaN)).toBe("0 B");
    });
  });

  describe("formatDuration", () => {
    it("should format millisecond durations accurately", () => {
      expect(formatDuration(500)).toBe("500ms");
      expect(formatDuration(1500)).toBe("1.50s");
      expect(formatDuration(65000)).toBe("65.00s");
    });

    it("should handle zero or undefined duration", () => {
      expect(formatDuration(0)).toBe("-");
      expect(formatDuration(undefined)).toBe("-");
    });
  });

  describe("formatPercent", () => {
    it("should format percentage strings", () => {
      expect(formatPercent(0.95456)).toBe("95%");
      expect(formatPercent(0)).toBe("0%");
      expect(formatPercent(undefined)).toBe("-");
    });
  });

  describe("formatTokens and formatCost", () => {
    it("should format token counts and costs", () => {
      expect(formatTokens(12345)).toBe("12,345");
      expect(formatTokens(undefined)).toBe("-");
      expect(formatCost(0.0521)).toBe("$0.0521");
      expect(formatCost(undefined)).toBe("$0.00");
    });
  });
});
