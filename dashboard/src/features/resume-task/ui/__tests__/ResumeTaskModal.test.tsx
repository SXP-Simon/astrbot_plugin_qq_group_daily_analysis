import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ResumeTaskModal } from "@/features/resume-task/ui/ResumeTaskModal";
import { fetchProviderList } from "@/entities/trace/api/traceApi";
import { fetchReportTemplates } from "@/entities/report/api/reportApi";

vi.mock("@/entities/trace/api/traceApi", () => ({ fetchProviderList: vi.fn() }));
vi.mock("@/entities/report/api/reportApi", () => ({ fetchReportTemplates: vi.fn() }));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchProviderList).mockResolvedValue([{ id: "example-model", name: "示例模型" }]);
  vi.mocked(fetchReportTemplates).mockResolvedValue([
    { id: "example-template", label: "示例模板" },
  ]);
});

it("保留模型和模板选择，按原契约提交且不提前关闭", async () => {
  const confirm = vi.fn();
  const cancel = vi.fn();
  render(<ResumeTaskModal open loading={false} onConfirm={confirm} onCancel={cancel} />);
  await waitFor(() => expect(screen.getByLabelText("模型")).not.toBeDisabled());
  fireEvent.change(screen.getByLabelText("模型"), { target: { value: "example-model" } });
  fireEvent.change(screen.getByLabelText("报告模板"), { target: { value: "example-template" } });
  fireEvent.click(screen.getByRole("button", { name: "开始续跑" }));
  expect(confirm).toHaveBeenCalledTimes(1);
  expect(confirm).toHaveBeenCalledWith("example-model", "example-template");
  expect(cancel).not.toHaveBeenCalled();
});

it("列表失败时明确提示，仍可按原配置续跑，并支持重试加载", async () => {
  vi.mocked(fetchProviderList).mockRejectedValueOnce(new Error("离线"));
  vi.mocked(fetchReportTemplates).mockRejectedValueOnce(new Error("离线"));
  const confirm = vi.fn();
  render(<ResumeTaskModal open loading={false} onConfirm={confirm} onCancel={vi.fn()} />);
  await screen.findByText(/模型列表暂时无法加载/);
  expect(screen.getByText(/无法确认模板支持情况/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "开始续跑" }));
  expect(confirm).toHaveBeenCalledWith(undefined, undefined);
  fireEvent.click(screen.getByRole("button", { name: "重试模型列表" }));
  fireEvent.click(screen.getByRole("button", { name: "重试模板列表" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(screen.getByRole("option", { name: /示例模型/ })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: /示例模板/ })).toBeInTheDocument();
});

it("提交期间阻止重复提交和误关，返回后保留选择", async () => {
  const confirm = vi.fn();
  const cancel = vi.fn();
  const view = render(
    <ResumeTaskModal open loading={false} onConfirm={confirm} onCancel={cancel} />,
  );
  await waitFor(() => expect(screen.getByLabelText("模型")).not.toBeDisabled());
  fireEvent.change(screen.getByLabelText("模型"), { target: { value: "example-model" } });
  view.rerender(<ResumeTaskModal open loading onConfirm={confirm} onCancel={cancel} />);
  fireEvent.click(screen.getByRole("button", { name: "正在提交…" }));
  fireEvent.keyDown(document.activeElement!, { key: "Escape" });
  expect(confirm).not.toHaveBeenCalled();
  expect(cancel).not.toHaveBeenCalled();
  view.rerender(
    <ResumeTaskModal
      open
      loading={false}
      error="续跑未成功，请稍后重试。"
      onConfirm={confirm}
      onCancel={cancel}
    />,
  );
  expect(screen.getByLabelText("模型")).toHaveValue("example-model");
  expect(screen.getByRole("alert")).toHaveTextContent("续跑未成功");
});

it("关闭再打开后，前次迟到的模型列表不能覆盖新列表", async () => {
  let resolve!: (value: Awaited<ReturnType<typeof fetchProviderList>>) => void;
  vi.mocked(fetchProviderList).mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const props = { loading: false, onConfirm: vi.fn(), onCancel: vi.fn() };
  const view = render(<ResumeTaskModal {...props} open />);
  view.rerender(<ResumeTaskModal {...props} open={false} />);
  view.rerender(<ResumeTaskModal {...props} open />);
  await waitFor(() => expect(screen.getByLabelText("模型")).not.toBeDisabled());
  await act(async () => resolve([{ id: "old", name: "过期模型" }]));
  expect(screen.queryByRole("option", { name: /过期模型/ })).not.toBeInTheDocument();
  expect(screen.getByRole("option", { name: /示例模型/ })).toBeInTheDocument();
});
