import { expect, it } from "vitest";
import { mockHandlers } from "@/mocks/handlers";
import { extractData } from "@/shared/api/bridge";
import { mockReportImageBytes } from "@/mocks/data/reportContent";
import type { ManagedFileContent } from "@/entities/plugin-data/api/managedFilesApi";
it("管理入口使用可读报告图片而非单像素占位，HTML 与报告页保持相同示例", () => {
  const image = extractData<ManagedFileContent>(
    mockHandlers["GET plugin-data/files/content"]({
      partition: "reports",
      name: "123456789_2026-11-03_miku.png",
    }),
  )!;
  const bytes = Uint8Array.from(atob(image.content_base64), (char) => char.charCodeAt(0));
  expect(bytes.length).toBe(mockReportImageBytes);
  const header = new DataView(bytes.buffer);
  expect(header.getUint32(16)).toBeGreaterThan(600);
  expect(header.getUint32(20)).toBeGreaterThan(500);
  const html = extractData<ManagedFileContent>(
    mockHandlers["GET plugin-data/files/content"]({
      partition: "reports",
      name: "123456789_2026-11-03.html",
    }),
  )!;
  expect(html.text).toContain("示例数据");
});
