import { describe, expect, it } from "vitest";
import { templateCdnProbeSchema } from "../cdnProbe";

describe("CDN 检测响应契约", () => {
  it("支持多份实际模板文件，不能用同一文件重复凑数", () => {
    const base = { url: "https://example.com/file", success: true, status_code: 200, elapsed_ms: 10, bytes_received: 100, error: null };
    const checks = [
      { ...base, id: "maria-png", label: "装饰图片", description: "Maria", kind: "gh" },
      { ...base, id: "atri-font", label: "报告字体", description: "ATRI", kind: "gh" },
      { ...base, id: "npm-css", label: "npm 兼容性", description: "额外检查", kind: "npm" },
    ];
    expect(templateCdnProbeSchema.safeParse({ base_url: "https://example.com", usable: true, checks }).success).toBe(true);
    expect(templateCdnProbeSchema.safeParse({ base_url: "https://example.com", usable: true, checks: [...checks, checks[0]] }).success).toBe(false);
  });

  it("拒绝缺少结果或把字符串当作成功标志的响应", () => {
    expect(templateCdnProbeSchema.safeParse({ status: "ok" }).success).toBe(false);
    expect(templateCdnProbeSchema.safeParse({ base_url: "https://example.com", usable: "true", checks: [] }).success).toBe(false);
  });

  it("拒绝重复资源类型和矛盾的成功汇总", () => {
    const check = { id: "maria-png", label: "装饰图片", description: "Maria 模板图片", kind: "gh", url: "https://example.com/gh/sample", success: true, status_code: 200, elapsed_ms: 10, bytes_received: 100, error: null };
    expect(templateCdnProbeSchema.safeParse({ base_url: "https://example.com", usable: true, checks: [check, check] }).success).toBe(false);
    expect(templateCdnProbeSchema.safeParse({ base_url: "https://example.com", usable: true, checks: [check, { ...check, id: "npm-css", kind: "npm", success: false }] }).success).toBe(false);
  });
});
