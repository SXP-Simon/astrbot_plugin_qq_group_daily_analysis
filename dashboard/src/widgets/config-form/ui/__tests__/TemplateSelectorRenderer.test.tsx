import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { useReportTemplates } from "../../../../entities/report/model/useReportTemplates";
import { fetchTemplatePreview } from "../../../../entities/report/api/reportApi";
import { TemplateSelectorRenderer } from "../TemplateSelectorRenderer";
import type { ReportTemplateItem } from "../../../../entities/report/model/templates";

vi.mock("../../../../entities/report/model/useReportTemplates", () => ({
  useReportTemplates: vi.fn(),
}));
vi.mock("../../../../entities/report/api/reportApi", () => ({ fetchTemplatePreview: vi.fn() }));
vi.mock("../../../../features/install-template/ui/TemplateInstallModal", () => ({
  TemplateInstallModal: ({ open, onInstalled }: { open: boolean; onInstalled: () => void }) =>
    open ? <button onClick={onInstalled}>完成安装示例</button> : null,
}));
vi.mock("../../../../features/install-template/ui/TemplateUninstallModal", () => ({
  TemplateUninstallModal: ({
    open,
    onUninstalled,
  }: {
    open: boolean;
    onUninstalled: (name: string) => void;
  }) => (open ? <button onClick={() => onUninstalled("custom")}>完成卸载示例</button> : null),
}));

const templates: ReportTemplateItem[] = [
  { id: "HatsuneMiku", label: "初音", has_image: true, has_html: true, has_typst: true },
  {
    id: "custom",
    label: "我的模板",
    display_name: "我的模板",
    is_custom: true,
    has_image: true,
    desc: "本地模板说明",
  },
  { id: "native", label: "仅原生模板", has_typst: true },
];
const refresh = vi.fn();
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useReportTemplates).mockReturnValue({
    templates,
    loading: false,
    ready: true,
    error: "",
    refresh,
  });
  vi.mocked(fetchTemplatePreview).mockResolvedValue("data:image/png;base64,example");
});

it("根据真实能力筛选画廊，应用保留配置回调且不自动改写旧值", () => {
  const change = vi.fn();
  render(
    <TemplateSelectorRenderer
      value="unknown"
      requirements={{ engine: "html", formats: ["image"] }}
      onChange={change}
    />,
  );
  expect(screen.getByText(/当前主题不支持/)).toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "浏览全部模板画廊" }));
  expect(screen.queryByRole("article", { name: "仅原生模板" })).not.toBeInTheDocument();
  const card = screen.getByRole("article", { name: "我的模板" });
  expect(within(card).getByText("本地模板说明")).toBeInTheDocument();
  fireEvent.click(within(card).getByRole("button", { name: "应用此模板" }));
  expect(change).toHaveBeenCalledWith("custom");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("内置预览跟随 CDN，画廊嵌套预览关闭后保留画廊并恢复入口焦点", async () => {
  render(
    <TemplateSelectorRenderer
      value="HatsuneMiku"
      cdnBaseUrl="https://cdn.example"
      onChange={vi.fn()}
    />,
  );
  expect(screen.getByRole("img", { name: /HatsuneMiku/ })).toHaveAttribute(
    "src",
    expect.stringContaining("https://cdn.example/gh/"),
  );
  fireEvent.click(screen.getByRole("button", { name: "浏览全部模板画廊" }));
  const trigger = within(screen.getByRole("article", { name: "我的模板" })).getByRole("button", {
    name: "预览 我的模板",
  });
  trigger.focus();
  fireEvent.click(trigger);
  const preview = screen.getByRole("dialog", { name: "模板预览 · 我的模板" });
  await waitFor(() =>
    expect(within(preview).getByRole("img", { hidden: true })).toHaveAttribute(
      "src",
      "data:image/png;base64,example",
    ),
  );
  fireEvent.keyDown(document.activeElement || document.body, { key: "Escape" });
  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: "模板预览 · 我的模板" })).not.toBeInTheDocument(),
  );
  expect(screen.getByRole("dialog", { name: "报告模板视觉样式画廊" })).toBeInTheDocument();
  await waitFor(() => expect(trigger).toHaveFocus());
});

it("搜索模板选择保留键盘入口，安装卸载刷新元数据且卸载当前值回到默认", async () => {
  const change = vi.fn();
  render(<TemplateSelectorRenderer value="custom" onChange={change} />);
  await waitFor(() =>
    expect(screen.getByRole("img", { name: "我的模板" })).toHaveAttribute(
      "src",
      "data:image/png;base64,example",
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: /^报告模板：/ }));
  const search = screen.getByRole("combobox", { name: "搜索报告模板" });
  fireEvent.change(search, { target: { value: "仅原生" } });
  fireEvent.keyDown(search, { key: "Enter" });
  expect(change).toHaveBeenCalledWith("native");
  fireEvent.click(screen.getByRole("button", { name: "安装模板" }));
  fireEvent.click(screen.getByRole("button", { name: "完成安装示例" }));
  expect(refresh).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("button", { name: "卸载模板" }));
  fireEvent.click(screen.getByRole("button", { name: "完成卸载示例" }));
  expect(refresh).toHaveBeenCalledTimes(2);
  expect(change).toHaveBeenLastCalledWith("HatsuneMiku");
});

it("读取失败可重试，空列表不虚构可选模板", () => {
  vi.mocked(useReportTemplates).mockReturnValue({
    templates: [],
    loading: false,
    ready: false,
    error: "模板列表读取失败",
    refresh,
  });
  const view = render(<TemplateSelectorRenderer value="HatsuneMiku" onChange={vi.fn()} />);
  expect(screen.getByRole("button", { name: /^报告模板：/ })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "重试" }));
  expect(refresh).toHaveBeenCalledOnce();
  vi.mocked(useReportTemplates).mockReturnValue({
    templates: [],
    loading: false,
    ready: true,
    error: "",
    refresh,
  });
  view.rerender(<TemplateSelectorRenderer value="HatsuneMiku" onChange={vi.fn()} />);
  expect(screen.getByText("暂无可用模板，请安装模板或刷新列表。")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "预览当前效果" })).toBeDisabled();
});

it("元数据刷新移除正在预览的模板时退出子预览，画廊仍可关闭", async () => {
  const change = vi.fn();
  const view = render(<TemplateSelectorRenderer value="HatsuneMiku" onChange={change} />);
  fireEvent.click(screen.getByRole("button", { name: "浏览全部模板画廊" }));
  fireEvent.click(
    within(screen.getByRole("article", { name: /HatsuneMiku/ })).getByRole("button", {
      name: /预览 HatsuneMiku/,
    }),
  );
  expect(screen.getByRole("dialog", { name: /模板预览/ })).toBeInTheDocument();
  vi.mocked(useReportTemplates).mockReturnValue({
    templates: [],
    loading: true,
    ready: false,
    error: "",
    refresh,
  });
  view.rerender(<TemplateSelectorRenderer value="HatsuneMiku" onChange={change} />);
  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: /模板预览/ })).not.toBeInTheDocument(),
  );
  expect(change).not.toHaveBeenCalled();
  fireEvent.keyDown(document.activeElement || document.body, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});
