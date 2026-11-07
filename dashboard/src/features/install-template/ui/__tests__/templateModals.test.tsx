import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { TemplateInstallModal } from "../TemplateInstallModal";
import { TemplateUninstallModal } from "../TemplateUninstallModal";
import {
  fetchReportTemplates,
  installTemplateFromFile,
  uninstallTemplate,
} from "../../../../entities/report/api/reportApi";

vi.mock("../../../../entities/report/api/reportApi", () => ({
  fetchReportTemplates: vi.fn(),
  installTemplateFromUrl: vi.fn(),
  installTemplateFromFile: vi.fn(),
  uninstallTemplate: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));
beforeEach(() => vi.resetAllMocks());

it("ZIP 拖入失败保留文件与名称，重试成功才关闭", async () => {
  const close = vi.fn(),
    installed = vi.fn();
  render(<TemplateInstallModal open onClose={close} onInstalled={installed} />);
  fireEvent.keyDown(screen.getByRole("tab", { name: "上传 ZIP" }), { key: "Enter" });
  const input = screen.getByLabelText("ZIP 压缩包");
  const file = new File(["zip"], "my-theme.zip");
  fireEvent.drop(input.closest("div")!, { dataTransfer: { files: [file] } });
  fireEvent.change(screen.getByLabelText("模板名（可选，留空自动推断）"), {
    target: { value: "my-theme" },
  });
  vi.mocked(installTemplateFromFile).mockRejectedValueOnce(new Error("压缩包缺少入口"));
  fireEvent.click(screen.getByRole("button", { name: "解压并安装" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("压缩包缺少入口");
  expect(screen.getByText(/my-theme.zip/)).toBeVisible();
  expect(screen.getByLabelText("模板名（可选，留空自动推断）")).toHaveValue("my-theme");
  expect(close).not.toHaveBeenCalled();
  vi.mocked(installTemplateFromFile).mockResolvedValueOnce({
    name: "my-theme",
    label: "示例",
    has_image: false,
    has_html: false,
    files: ["report.typ"],
  });
  fireEvent.click(screen.getByRole("button", { name: "解压并安装" }));
  await waitFor(() => expect(close).toHaveBeenCalledOnce());
  expect(installed).toHaveBeenCalledOnce();
});

it("卸载需要明确确认，失败停留原目标，返回保留列表", async () => {
  vi.mocked(fetchReportTemplates).mockResolvedValue([
    { id: "custom", label: "自定义示例", can_uninstall: true },
    { id: "builtin", label: "内置示例", can_uninstall: false },
  ]);
  const close = vi.fn();
  render(<TemplateUninstallModal open onClose={close} />);
  await screen.findByText("自定义示例");
  expect(screen.queryByText("内置示例")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "卸载" }));
  expect(uninstallTemplate).not.toHaveBeenCalled();
  vi.mocked(uninstallTemplate).mockRejectedValueOnce(new Error("权限不足"));
  fireEvent.click(screen.getByRole("button", { name: "卸载整个模板" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("权限不足");
  expect(within(screen.getByRole("dialog")).getByText("custom/")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "返回列表" }));
  expect(screen.getByRole("button", { name: "卸载" })).toBeEnabled();
  expect(close).not.toHaveBeenCalled();
});
