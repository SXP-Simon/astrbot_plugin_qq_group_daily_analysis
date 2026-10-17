import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../../../../shared/api/bridge";
import { fetchComicTemplatePreview } from "../comicTemplateApi";

vi.mock("../../../../shared/api/bridge", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../../shared/api/bridge")>();
  return { ...original, apiGet: vi.fn() };
});

const get = vi.mocked(apiGet);
const thumbnail = "data:image/webp;base64,dGh1bWI=";
const full = "data:image/webp;base64,ZnVsbA==";

describe("漫画模板示例图 API", () => {
  beforeEach(() => vi.clearAllMocks());

  it("兼容 Bridge 的双层包装并按图片尺寸分别缓存", async () => {
    get.mockResolvedValueOnce({ data: { data: { data_url: thumbnail } } });
    expect(await fetchComicTemplatePreview("wrapped", "thumbnail")).toBe(thumbnail);
    expect(await fetchComicTemplatePreview("wrapped", "thumbnail")).toBe(thumbnail);
    get.mockResolvedValueOnce({ data_url: full });
    expect(await fetchComicTemplatePreview("wrapped", "full")).toBe(full);
    expect(get).toHaveBeenNthCalledWith(1, "comic/templates/preview", { template_name: "wrapped", variant: "thumbnail" });
    expect(get).toHaveBeenNthCalledWith(2, "comic/templates/preview", { template_name: "wrapped", variant: "full" });
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("明确接受无示例图，不把错误响应或任意 URL 当图片", async () => {
    get.mockResolvedValueOnce({ data: { data_url: null } });
    expect(await fetchComicTemplatePreview("empty")).toBeNull();
    get.mockResolvedValueOnce({ status: "error", message: "未知漫画模板" });
    await expect(fetchComicTemplatePreview("unknown")).rejects.toThrow("未知漫画模板");
    get.mockResolvedValueOnce({ data: { data_url: "https://example.com/fake.png" } });
    await expect(fetchComicTemplatePreview("invalid")).rejects.toThrow("未收到有效的漫画示例图响应");
  });

  it("失败不会缓存，用户重试可重新获取已缓存但无法显示的图片", async () => {
    get.mockRejectedValueOnce(new Error("网络失败"));
    await expect(fetchComicTemplatePreview("retry", "thumbnail")).rejects.toThrow("网络失败");
    get.mockResolvedValueOnce({ data: { data_url: thumbnail } });
    expect(await fetchComicTemplatePreview("retry", "thumbnail")).toBe(thumbnail);
    get.mockResolvedValueOnce({ data: { data_url: full } });
    expect(await fetchComicTemplatePreview("retry", "thumbnail", true)).toBe(full);
    expect(get).toHaveBeenCalledTimes(3);
  });
});
