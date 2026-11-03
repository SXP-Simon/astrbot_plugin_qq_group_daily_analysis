import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { downloadTemplateResource, fetchTemplateResources } from "../../../../entities/config/api/templateResourceApi";
import { useTemplateResources } from "../useTemplateResources";

vi.mock("../../../../entities/config/api/templateResourceApi", () => ({ fetchTemplateResources: vi.fn(), downloadTemplateResource: vi.fn() }));
const snapshot = {
  directory: "data/typst/resources", groups: [
    { theme: "scrapbook", files: [{ name: "scrapbook/assistant.jpg", available: false }, { name: "scrapbook/star.svg", available: true }] },
    { theme: "hack", files: [{ name: "hack/globe.svg", available: false }] },
  ],
};

beforeEach(() => { vi.resetAllMocks(); vi.mocked(fetchTemplateResources).mockResolvedValue(snapshot); });

describe("按主题下载素材", () => {
  it("按需下载、保留成功项，切换CDN后仅重试失败文件", async () => {
    vi.mocked(downloadTemplateResource).mockRejectedValueOnce(new Error("CDN 超时"))
      .mockImplementation(async (name) => ({ name, available: true }));
    const { result, rerender } = renderHook(({ cdn }) => useTemplateResources(cdn), { initialProps: { cdn: "https://cdn.jsdmirror.com" } });
    await waitFor(() => expect(result.current.status).not.toBeNull());
    await act(async () => { await result.current.download(); });
    expect(result.current.progress.done).toBe(2);
    expect(result.current.progress.failed).toEqual([{ name: "scrapbook/assistant.jpg", message: "CDN 超时" }]);
    expect(result.current.status?.groups[1].files[0].available).toBe(true);
    rerender({ cdn: "https://fastly.jsdelivr.net" });
    await act(async () => { await result.current.download("scrapbook"); });
    expect(downloadTemplateResource).toHaveBeenCalledTimes(3);
    expect(downloadTemplateResource).toHaveBeenLastCalledWith("scrapbook/assistant.jpg", "https://fastly.jsdelivr.net");
    expect(result.current.progress).toEqual({ done: 1, total: 1, failed: [] });
  });

  it("最多三个并发，离开页面后不再启动队列中的文件", async () => {
    vi.mocked(fetchTemplateResources).mockResolvedValue({ directory: "data", groups: [{ theme: "test", files: Array.from({ length: 8 }, (_, index) => ({ name: `test/${index}.svg`, available: false })) }] });
    const finish: (() => void)[] = [];
    vi.mocked(downloadTemplateResource).mockImplementation((name) => new Promise((resolve) => finish.push(() => resolve({ name, available: true }))));
    const { result, unmount } = renderHook(() => useTemplateResources("https://fastly.jsdelivr.net"));
    await waitFor(() => expect(result.current.status).not.toBeNull());
    let running: Promise<void> | undefined;
    act(() => { running = result.current.download(); });
    await waitFor(() => expect(downloadTemplateResource).toHaveBeenCalledTimes(3));
    unmount();
    await act(async () => { finish.forEach((resolve) => resolve()); await running; });
    expect(downloadTemplateResource).toHaveBeenCalledTimes(3);
  });

  it("非法CDN不会发起下载，并给出可修正的提示", async () => {
    const { result } = renderHook(() => useTemplateResources("https://cdn.example/path"));
    await waitFor(() => expect(result.current.status).not.toBeNull());
    await act(async () => { await result.current.download("hack"); });
    expect(downloadTemplateResource).not.toHaveBeenCalled();
    expect(result.current.error).toContain("完整的网站地址");
  });
});
