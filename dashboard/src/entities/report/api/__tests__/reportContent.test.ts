import { afterEach, expect, it, vi } from "vitest";
import { fetchReportContent } from "@/entities/report/api/reportApi";
import { fetchManagedContent } from "@/entities/plugin-data/api/managedFilesApi";
import { apiGet } from "@/shared/api/bridge";
vi.mock("@/shared/api/bridge", async (original) => ({
  ...(await original<typeof import("@/shared/api/bridge")>()),
  apiGet: vi.fn(),
}));
afterEach(() => vi.resetAllMocks());
it("报告接收不重复传输 Base64 的 HTML，不因传输超过三十秒主动失败", async () => {
  const report = {
    filename: "example.html",
    size_bytes: 20,
    modified_at: 1,
    html_content: "<h1>示例</h1>",
  };
  vi.mocked(apiGet).mockResolvedValue({ data: report });
  expect(await fetchReportContent(report.filename)).toEqual(report);
  expect(apiGet).toHaveBeenCalledWith("reports/content", { filename: report.filename });
});
it("文件管理读取持续等待并保留真实修订号", async () => {
  const file = {
    name: "image.png",
    content_base64: "YWJj",
    text: null,
    media_type: "image/png",
    revision: "real-sha",
  };
  vi.mocked(apiGet).mockResolvedValue({ data: file });
  expect(await fetchManagedContent("reports", file.name)).toEqual(file);
  expect(apiGet).toHaveBeenCalledWith("plugin-data/files/content", {
    partition: "reports",
    name: file.name,
  });
});
