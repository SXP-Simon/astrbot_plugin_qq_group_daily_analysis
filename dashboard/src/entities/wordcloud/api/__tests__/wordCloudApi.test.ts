import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost, type ApiResponse } from "../../../../shared/api/bridge";
import { DEFAULT_WORDCLOUD_OPTIONS } from "../../model/types";
import { fetchWordCloudCatalog, fetchWordCloudSnapshots, previewWordCloud, previewWordCloudFont } from "../wordCloudApi";

vi.mock("../../../../shared/api/bridge", async (original) => ({
  ...await original<typeof import("../../../../shared/api/bridge")>(),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => { vi.useFakeTimers(); vi.resetAllMocks(); });
afterEach(() => { vi.useRealTimers(); });

describe("词云预览请求的等待边界", () => {
  it("宿主 HTML 请求不回包时结束等待，迟到响应不能替代重试结果", async () => {
    const old = deferred<ApiResponse>();
    vi.mocked(apiPost).mockReturnValueOnce(old.promise).mockResolvedValueOnce({ data: { html: "重试预览" } });
    const first = previewWordCloud(DEFAULT_WORDCLOUD_OPTIONS, "html");
    const timedOut = expect(first).rejects.toThrow("请求词云预览超时");
    await vi.advanceTimersByTimeAsync(30000);
    await timedOut;
    expect(await previewWordCloud(DEFAULT_WORDCLOUD_OPTIONS, "html")).toEqual({ html: "重试预览" });
    old.resolve({ data: { html: "旧预览" } });
    await expect(first).rejects.toThrow("请求词云预览超时");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("T2I 允许等待渲染队列，超过两分钟仍未回包时给出失败", async () => {
    vi.mocked(apiPost).mockReturnValue(new Promise(() => {}));
    let settled = false;
    const preview = previewWordCloud(DEFAULT_WORDCLOUD_OPTIONS, "image");
    const timedOut = expect(preview).rejects.toThrow("T2I 图片预览超时");
    void preview.then(() => { settled = true; }, () => { settled = true; });
    await vi.advanceTimersByTimeAsync(119999);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    await timedOut;
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each(["catalog", "snapshots", "font"])("%s 读取超时不会无限占用加载状态", async (kind) => {
    vi.mocked(apiGet).mockReturnValue(new Promise(() => {}));
    vi.mocked(apiPost).mockReturnValue(new Promise(() => {}));
    const result = kind === "catalog" ? fetchWordCloudCatalog() : kind === "snapshots" ? fetchWordCloudSnapshots() : previewWordCloudFont("wenkai");
    const timedOut = expect(result).rejects.toThrow("超时");
    await vi.advanceTimersByTimeAsync(30000);
    await timedOut;
    expect(vi.getTimerCount()).toBe(0);
  });

  it("正常回包和明确失败都会清理请求计时器", async () => {
    vi.mocked(apiPost).mockResolvedValueOnce({ data: { html: "预览" } }).mockRejectedValueOnce(new Error("连接已断开"));
    expect(await previewWordCloud(DEFAULT_WORDCLOUD_OPTIONS, "html")).toEqual({ html: "预览" });
    await expect(previewWordCloud(DEFAULT_WORDCLOUD_OPTIONS, "html")).rejects.toThrow("连接已断开");
    expect(vi.getTimerCount()).toBe(0);
  });
});
