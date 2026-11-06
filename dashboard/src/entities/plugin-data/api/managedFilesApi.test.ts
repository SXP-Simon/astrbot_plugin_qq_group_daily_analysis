import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchManagedPartitions, mutateManagedFile } from "./managedFilesApi";
import { apiGet, apiPost } from "../../../shared/api/bridge";

vi.mock("../../../shared/api/bridge", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../shared/api/bridge")>()),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));
afterEach(() => vi.clearAllMocks());

describe("文件管理 API", () => {
  it("拒绝无响应，避免把读取失败展示成空分区", async () => {
    vi.mocked(apiGet).mockResolvedValue(null);
    await expect(fetchManagedPartitions()).rejects.toThrow();
  });
  it("保留后端修订冲突原因，不误报保存成功", async () => {
    vi.mocked(apiPost).mockResolvedValue({
      status: "ok",
      data: { status: "error", message: "文件已变更，请刷新" },
    });
    await expect(
      mutateManagedFile({
        partition: "custom_templates",
        name: "demo/report.typ",
        operation: "replace",
        revision: "old",
        content_base64: "SGk=",
      }),
    ).rejects.toThrow("文件已变更，请刷新");
  });
});
