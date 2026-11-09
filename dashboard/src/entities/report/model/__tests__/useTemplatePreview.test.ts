import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { fetchTemplatePreview } from "@/entities/report/api/reportApi";
import { useTemplatePreview } from "@/entities/report/model/useTemplatePreview";

vi.mock("@/entities/report/api/reportApi", () => ({ fetchTemplatePreview: vi.fn() }));
beforeEach(() => vi.resetAllMocks());

it("内置预览使用当前 CDN，自定义读取仅在启用时发生", async () => {
  const { result, rerender } = renderHook(
    ({ custom, enabled }) => useTemplatePreview("demo", custom, "https://cdn.example", enabled),
    { initialProps: { custom: false, enabled: true } },
  );
  expect(result.current.src).toMatch(/^https:\/\/cdn.example\/gh\/.*\/assets\/demo-demo.webp$/);
  expect(fetchTemplatePreview).not.toHaveBeenCalled();
  rerender({ custom: true, enabled: false });
  expect(result.current.src).toBeNull();
  expect(fetchTemplatePreview).not.toHaveBeenCalled();
  vi.mocked(fetchTemplatePreview).mockResolvedValue("data:image/png;base64,example");
  rerender({ custom: true, enabled: true });
  await waitFor(() => expect(result.current.src).toBe("data:image/png;base64,example"));
  expect(fetchTemplatePreview).toHaveBeenCalledWith("demo");
});

it("切换模板后旧请求不覆盖新图片，关闭后也不接收旧结果", async () => {
  let finish!: (value: string | null) => void;
  vi.mocked(fetchTemplatePreview)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    )
    .mockResolvedValueOnce("second.png");
  const { result, rerender } = renderHook(
    ({ id, enabled }) => useTemplatePreview(id, true, null, enabled),
    { initialProps: { id: "first", enabled: true } },
  );
  rerender({ id: "second", enabled: true });
  expect(result.current.src).toBeNull();
  await waitFor(() => expect(result.current.src).toBe("second.png"));
  await act(async () => finish("first.png"));
  expect(result.current.src).toBe("second.png");
  rerender({ id: "second", enabled: false });
  expect(result.current.src).toBeNull();
});

it("缺图和读取失败显式反馈，内置地址无效时不请求默认站点", async () => {
  vi.mocked(fetchTemplatePreview)
    .mockResolvedValueOnce(null)
    .mockRejectedValueOnce(new Error("offline"));
  const { result, rerender } = renderHook(({ id }) => useTemplatePreview(id, true, null), {
    initialProps: { id: "missing" },
  });
  await waitFor(() => expect(result.current.error).toContain("没有可用"));
  rerender({ id: "failed" });
  await waitFor(() => expect(result.current.error).toContain("读取失败"));
  const builtin = renderHook(() => useTemplatePreview("HatsuneMiku", false, null));
  expect(builtin.result.current.src).toBeNull();
  expect(builtin.result.current.error).toContain("CDN 地址无效");
});
