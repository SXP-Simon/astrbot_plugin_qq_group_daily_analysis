import { useState } from "react";
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { RerenderReportModal } from "@/features/rerender-report/ui/RerenderReportModal";
import { useRerenderReport } from "@/features/rerender-report/model/useRerenderReport";
import { fetchReportTemplates, rerenderReport } from "@/entities/report/api/reportApi";
import type { ReportItem } from "@/entities/report/model/types";
import type { ReportTemplateItem } from "@/entities/report/model/templates";

vi.mock("@/entities/report/api/reportApi", () => ({
  fetchReportTemplates: vi.fn(),
  rerenderReport: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), warning: vi.fn() } }));

const report: ReportItem = {
  filename: "示例报告.jpg",
  size_bytes: 1024,
  modified_at: 1760000000,
  group_id: "demo-group",
  group_name: "示例群聊",
  platform: "telegram-main",
  trace_id: "trace-demo",
};
const imageTemplates = [
  { id: "HatsuneMiku", label: "初音", has_image: true },
  { id: "custom-image", label: "自定义图片", has_image: true, is_custom: true },
];
const result = {
  success: true,
  filename: "新示例报告.jpg",
  report_path: "reports/new.jpg",
  is_html: false,
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}
function Fixture({ onSuccess = vi.fn() }: { onSuccess?: () => void | Promise<unknown> }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>换模板</button>
      <RerenderReportModal
        open={open}
        report={report}
        onClose={() => setOpen(false)}
        onSuccess={onSuccess}
      />
    </>
  );
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchReportTemplates).mockImplementation(async (format) =>
    format === "html"
      ? [{ id: "custom-web", label: "自定义网页", has_html: true, is_custom: true }]
      : imageTemplates,
  );
  vi.mocked(rerenderReport).mockResolvedValue(result);
});

it("保留平台与任务信息，禁止重复提交和中途关闭，完成后通知并恢复焦点", async () => {
  const pending = deferred<Awaited<ReturnType<typeof rerenderReport>>>();
  vi.mocked(rerenderReport).mockReturnValueOnce(pending.promise);
  const refreshed = vi.fn();
  render(<Fixture onSuccess={refreshed} />);
  const trigger = screen.getByRole("button", { name: "换模板" });
  act(() => trigger.focus());
  fireEvent.click(trigger);
  const submit = screen.getByRole("button", { name: "生成新报告" });
  await waitFor(() => expect(submit).toBeEnabled());
  expect(screen.getByLabelText("输出格式")).toHaveFocus();
  fireEvent.change(screen.getByLabelText("报告模板"), { target: { value: "custom-image" } });
  fireEvent.click(submit);
  fireEvent.submit(screen.getByRole("form", { name: "重绘报告" }));
  expect(rerenderReport).toHaveBeenCalledTimes(1);
  expect(rerenderReport).toHaveBeenCalledWith({
    group_id: "demo-group",
    platform_id: "telegram-main",
    trace_id: "trace-demo",
    template_name: "custom-image",
    render_format: "image",
  });
  expect(screen.getByRole("button", { name: "取消" })).toBeDisabled();
  expect(screen.getByLabelText("输出格式")).toBeDisabled();
  fireEvent.keyDown(document, { key: "Escape" });
  fireEvent.click(screen.getByRole("button", { name: "关闭" }));
  expect(screen.getByRole("dialog", { name: "换模板重绘" })).toBeVisible();
  await act(async () => pending.resolve(result));
  expect(refreshed).toHaveBeenCalledOnce();
  expect(toast.success).toHaveBeenCalledWith("新报告已生成", { description: result.filename });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(trigger).toHaveFocus();
});

it("请求失败在表单内说明原因，保留用户选择后可重试", async () => {
  vi.mocked(rerenderReport).mockRejectedValueOnce(new Error("未找到这次分析的完整产物记录"));
  render(<RerenderReportModal open report={report} onClose={vi.fn()} onSuccess={vi.fn()} />);
  const submit = screen.getByRole("button", { name: "生成新报告" });
  await waitFor(() => expect(submit).toBeEnabled());
  fireEvent.change(screen.getByLabelText("报告模板"), { target: { value: "custom-image" } });
  fireEvent.click(submit);
  expect(await screen.findByRole("alert")).toHaveTextContent("未找到这次分析的完整产物记录");
  expect(screen.getByLabelText("报告模板")).toHaveValue("custom-image");
  expect(toast.success).not.toHaveBeenCalled();
  fireEvent.click(submit);
  await waitFor(() => expect(toast.success).toHaveBeenCalledOnce());
  expect(rerenderReport).toHaveBeenCalledTimes(2);
});

it("切换输出格式清除旧能力但保留显式选择，旧请求不能覆盖网页模板", async () => {
  const slow = deferred<ReportTemplateItem[]>();
  vi.mocked(fetchReportTemplates).mockReturnValueOnce(slow.promise);
  render(<RerenderReportModal open report={report} onClose={vi.fn()} onSuccess={vi.fn()} />);
  expect(screen.getByRole("button", { name: "生成新报告" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("输出格式"), { target: { value: "html" } });
  await waitFor(() => expect(screen.getByLabelText("报告模板")).toHaveValue("custom-web"));
  await act(async () => slow.resolve(imageTemplates));
  expect(screen.queryByRole("option", { name: /初音/ })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("报告模板"), { target: { value: "custom-web" } });
  fireEvent.change(screen.getByLabelText("输出格式"), { target: { value: "image" } });
  expect(screen.getByRole("button", { name: "生成新报告" })).toBeDisabled();
  expect(await screen.findByText("原选模板不支持当前格式，请重新选择。")).toBeVisible();
  expect(screen.getByLabelText("报告模板")).toHaveValue("custom-web");
  fireEvent.change(screen.getByLabelText("报告模板"), { target: { value: "custom-image" } });
  expect(screen.getByRole("button", { name: "生成新报告" })).toBeEnabled();
});

it("模板加载失败可重试，空列表不虚构可用模板，缺失群号不能发送请求", async () => {
  vi.mocked(fetchReportTemplates)
    .mockRejectedValueOnce(new Error("离线"))
    .mockResolvedValueOnce([]);
  const view = render(
    <RerenderReportModal open report={report} onClose={vi.fn()} onSuccess={vi.fn()} />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "重新加载模板" }));
  expect(await screen.findByText("没有支持该格式的模板，请切换输出格式。")).toBeVisible();
  fireEvent.submit(screen.getByRole("form", { name: "重绘报告" }));
  expect(rerenderReport).not.toHaveBeenCalled();
  view.rerender(
    <RerenderReportModal
      open
      report={{ ...report, group_id: null }}
      onClose={vi.fn()}
      onSuccess={vi.fn()}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("这份报告没有群聊记录");
  expect(screen.getByRole("button", { name: "生成新报告" })).toBeDisabled();
});

it("按 HTML 文件扩展名初始化输出格式，关闭重开清除上次选择", async () => {
  const close = vi.fn();
  const props = {
    report: { ...report, filename: "示例.htm", is_html: false },
    onClose: close,
    onSuccess: vi.fn(),
  };
  const view = render(<RerenderReportModal {...props} open />);
  expect(screen.getByLabelText("输出格式")).toHaveValue("html");
  await waitFor(() => expect(screen.getByRole("button", { name: "生成新报告" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("输出格式"), { target: { value: "image" } });
  view.rerender(<RerenderReportModal {...props} open={false} />);
  view.rerender(<RerenderReportModal {...props} open />);
  expect(screen.getByLabelText("输出格式")).toHaveValue("html");
  await waitFor(() => expect(screen.getByRole("button", { name: "生成新报告" })).toBeEnabled());
  fireEvent.keyDown(document, { key: "Escape" });
  expect(close).toHaveBeenCalledOnce();
});

it("不把空回执或未生成文件当成成功，保留表单供用户确认与重试", async () => {
  vi.mocked(rerenderReport)
    .mockResolvedValueOnce(null)
    .mockResolvedValueOnce({ ...result, filename: "" });
  const close = vi.fn();
  render(<RerenderReportModal open report={report} onClose={close} onSuccess={vi.fn()} />);
  const submit = screen.getByRole("button", { name: "生成新报告" });
  await waitFor(() => expect(submit).toBeEnabled());
  for (let index = 0; index < 2; index++) {
    fireEvent.click(submit);
    expect(await screen.findByRole("alert")).toHaveTextContent("未收到新报告的生成结果");
  }
  expect(close).not.toHaveBeenCalled();
  expect(toast.success).not.toHaveBeenCalled();
});

it("切换报告或卸载使旧生成请求失效，旧结果不关闭新表单或覆盖新错误", async () => {
  const first = deferred<Awaited<ReturnType<typeof rerenderReport>>>();
  const second = deferred<Awaited<ReturnType<typeof rerenderReport>>>();
  vi.mocked(rerenderReport).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  const close = vi.fn();
  const refresh = vi.fn();
  const view = renderHook(({ item }) => useRerenderReport(true, item, close, refresh), {
    initialProps: { item: report },
  });
  await waitFor(() => expect(view.result.current.canSubmit).toBe(true));
  let oldSubmit!: Promise<void>;
  act(() => {
    oldSubmit = view.result.current.submit();
  });
  view.rerender({ item: { ...report, filename: "下一份报告.jpg", trace_id: "next-trace" } });
  await waitFor(() => expect(view.result.current.canSubmit).toBe(true));
  let newSubmit!: Promise<void>;
  act(() => {
    newSubmit = view.result.current.submit();
  });
  await act(async () => {
    first.resolve(result);
    await oldSubmit;
  });
  expect(view.result.current.submitting).toBe(true);
  expect(close).not.toHaveBeenCalled();
  expect(refresh).not.toHaveBeenCalled();
  expect(toast.success).not.toHaveBeenCalled();
  view.unmount();
  await act(async () => {
    second.reject(new Error("迟到的失败"));
    await newSubmit;
  });
  expect(close).not.toHaveBeenCalled();
  expect(toast.success).not.toHaveBeenCalled();
});

it("生成成功后的列表刷新失败单独提示，不误报重绘失败", async () => {
  const close = vi.fn();
  const refresh = vi.fn().mockRejectedValue(new Error("列表不可用"));
  const view = renderHook(() => useRerenderReport(true, report, close, refresh));
  await waitFor(() => expect(view.result.current.canSubmit).toBe(true));
  await act(() => view.result.current.submit());
  expect(close).toHaveBeenCalledOnce();
  expect(toast.success).toHaveBeenCalledOnce();
  expect(toast.warning).toHaveBeenCalledWith("新报告已生成，列表未能更新。请手动刷新查看。");
  expect(view.result.current.submitError).toBe("");
});
