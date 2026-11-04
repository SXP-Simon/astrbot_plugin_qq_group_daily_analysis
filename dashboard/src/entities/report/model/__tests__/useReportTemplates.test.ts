import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchReportTemplates } from "../../api/reportApi";
import { useReportTemplates } from "../useReportTemplates";
import type { ReportTemplateItem } from "../templates";

vi.mock("../../api/reportApi", () => ({ fetchReportTemplates: vi.fn() }));
beforeEach(() => vi.resetAllMocks());

describe("模板能力列表", () => {
  it("空列表和请求失败均不虚构内置模板，重试后恢复", async () => {
    vi.mocked(fetchReportTemplates).mockResolvedValueOnce([]).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([{ id: "native", label: "原生", has_typst: true }]);
    const { result } = renderHook(() => useReportTemplates());
    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.templates).toEqual([]);
    await act(() => result.current.refresh());
    expect(result.current.ready).toBe(false);
    expect(result.current.error).toContain("重试");
    expect(result.current.templates).toEqual([]);
    await act(() => result.current.refresh());
    expect(result.current.templates[0].id).toBe("native");
  });

  it("切换输出格式立即隐藏旧能力，晚到的旧请求不能覆盖新结果", async () => {
    let finishOld!: (items: ReportTemplateItem[]) => void;
    vi.mocked(fetchReportTemplates).mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; })).mockResolvedValueOnce([{ id: "web", label: "网页", has_html: true }]);
    const { result, rerender } = renderHook(({ format }: { format: "html" | "image" }) => useReportTemplates(format), { initialProps: { format: "image" } });
    rerender({ format: "html" });
    expect(result.current.templates).toEqual([]);
    await waitFor(() => expect(result.current.templates[0]?.id).toBe("web"));
    await act(async () => finishOld([{ id: "native", label: "原生", has_typst: true }]));
    expect(result.current.templates[0].id).toBe("web");
  });
});
