import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ManagedFilesPanel } from "../ManagedFilesPanel";
import { TemplatePackages } from "../../../../../features/install-template/ui/TemplatePackages";
import {
  fetchManagedContent,
  fetchManagedFiles,
  fetchManagedPartitions,
  mutateManagedFile,
} from "../../../../../entities/plugin-data/api/managedFilesApi";
import {
  fetchReportTemplates,
  uninstallTemplate,
} from "../../../../../entities/report/api/reportApi";

vi.mock("../../../../../entities/plugin-data/api/managedFilesApi", () => ({
  fetchManagedContent: vi.fn(),
  fetchManagedFiles: vi.fn(),
  fetchManagedPartitions: vi.fn(),
  mutateManagedFile: vi.fn(),
  deleteManagedFiles: vi.fn(),
}));
vi.mock("../../../../../entities/report/api/reportApi", () => ({
  fetchReportTemplates: vi.fn(),
  uninstallTemplate: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(fetchManagedPartitions).mockResolvedValue([
    {
      key: "custom_templates",
      name: "自定义报告模板",
      directory: "/data/templates",
      description: "模板源码",
      impact: "后续渲染生效",
      count: 1,
      size_bytes: 5,
      writable: true,
      deletable: true,
    },
  ]);
  vi.mocked(fetchManagedFiles).mockResolvedValue({
    items: [
      {
        name: "demo/report.typ",
        size_bytes: 5,
        modified_at: 1,
        media_type: "text/plain",
        editable: true,
        downloadable: true,
        revision: "stat:original",
      },
    ],
    total: 1,
    groups: [{ directory: "demo", count: 3, size_bytes: 20 }],
  });
  vi.mocked(fetchReportTemplates).mockResolvedValue([
    {
      id: "demo",
      label: "我的模板",
      display_name: "我的模板",
      is_custom: true,
      has_typst: true,
      can_uninstall: true,
    },
  ]);
  vi.mocked(fetchManagedContent).mockResolvedValue({
    name: "demo/report.typ",
    text: "Hello",
    content_base64: "SGVsbG8=",
    media_type: "text/plain",
    revision: "original",
  });
  const computedStyle = window.getComputedStyle.bind(window);
  vi.spyOn(window, "getComputedStyle").mockImplementation((element) => computedStyle(element));
  vi.stubGlobal(
    "URL",
    class extends URL {
      static createObjectURL() {
        return "blob:preview";
      }
      static revokeObjectURL() {}
    },
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

async function modalLayer(title: string) {
  return screen.findByRole("dialog", { name: title });
}

async function selectTemplate(label = "我的模板（demo）") {
  await screen.findByRole("button", { name: /^选择自定义模板：/ });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /^选择自定义模板：/ }));
  });
  await screen.findByRole("option", { name: label });
  await act(async () => {
    fireEvent.click(screen.getByRole("option", { name: label }));
  });
}

it("详情与子编辑弹窗保持关联，关闭编辑后仍可查看详情", async () => {
  render(
    <>
      <ManagedFilesPanel />
    </>,
  );
  await screen.findByText("管理");
  await act(async () => {
    fireEvent.click(screen.getByText("管理"));
  });
  await selectTemplate();
  await screen.findByText("查看 / 编辑");
  await act(async () => {
    fireEvent.click(screen.getByText("查看 / 编辑"));
  });
  const detail = await modalLayer("demo/report.typ");
  const drawer = screen.getByText("存储目录").closest<HTMLElement>('[role="dialog"]')!;
  expect(detail).toBeVisible();
  expect(drawer).toBeInTheDocument();
  await act(async () => {
    fireEvent.click(within(detail).getByText("编辑源码"));
  });
  const editor = await modalLayer("替换或编辑文件");
  expect(editor).toBeVisible();
  await act(async () => {
    fireEvent.click(within(editor).getByText(/取.?消/));
  });
  await waitFor(() => expect(editor).not.toBeVisible());
  expect(detail).toBeVisible();
  await act(async () => {
    fireEvent.click(within(detail).getByText("重命名"));
  });
  const rename = await modalLayer("重命名文件");
  expect(rename).toBeVisible();
}, 20000);

it("从抽屉新建源码与安装模板时，弹窗显示在抽屉上方", async () => {
  render(
    <>
      <ManagedFilesPanel />
    </>,
  );
  await screen.findByText("管理");
  await act(async () => {
    fireEvent.click(screen.getByText("管理"));
  });
  await screen.findByText("新建模板源码");
  await act(async () => {
    fireEvent.click(screen.getByText("新建模板源码"));
  });
  const editor = await modalLayer("上传或新建文件");
  const drawer = screen.getByText("存储目录").closest<HTMLElement>('[role="dialog"]')!;
  expect(editor).toBeVisible();
  await act(async () => {
    fireEvent.click(within(editor).getByText(/取.?消/));
  });
  await act(async () => {
    fireEvent.click(screen.getByText("安装模板包"));
  });
  const install = await screen.findByRole("dialog", { name: "安装自定义报告模板" });
  expect(install).toBeVisible();
  await waitFor(() => expect(install).toContainElement(document.activeElement as HTMLElement));
  await act(async () => {
    fireEvent.keyDown(install, { key: "Escape" });
  });
  await waitFor(() => expect(install).not.toBeVisible());
  expect(drawer).toBeVisible();
}, 20000);

it("模板类型直接可见且筛选传给接口，报告区只提供相关类型", async () => {
  const template = (await fetchManagedPartitions())[0];
  vi.mocked(fetchManagedPartitions).mockResolvedValue([
    template,
    { ...template, key: "reports", name: "历史报告文件", writable: false },
  ]);
  render(
    <>
      <ManagedFilesPanel />
    </>,
  );
  fireEvent.click(
    within((await screen.findByText("自定义报告模板")).closest("tr")!).getByText("管理"),
  );
  await selectTemplate();
  expect(screen.getByText("3 个文件 · 20 B")).toBeVisible();
  const filters = document.querySelector<HTMLElement>('[role="group"][aria-label="文件类型筛选"]')!;
  const typ = within(filters).getByText("Typst 模板（.typ）").closest("button")!;
  expect(typ).toBeVisible();
  await act(async () => {
    fireEvent.click(typ);
  });
  await waitFor(() =>
    expect(fetchManagedFiles).toHaveBeenLastCalledWith("custom_templates", "", 1, "typ", "demo"),
  );
  expect(typ).toHaveAttribute("aria-pressed", "true");
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "关闭分区" }));
  });
  await act(async () => {
    fireEvent.click(within(screen.getByText("历史报告文件").closest("tr")!).getByText("管理"));
  });
  const reportFilters = document.querySelector<HTMLElement>(
    '[role="group"][aria-label="文件类型筛选"]',
  )!;
  expect(within(reportFilters).queryByText(/Typst/)).toBeNull();
  await act(async () => {
    fireEvent.click(within(reportFilters).getByText("JPG + PNG"));
  });
  await waitFor(() =>
    expect(fetchManagedFiles).toHaveBeenLastCalledWith("reports", "", 1, "jpg,jpeg,png", ""),
  );
}, 20000);

it("包内新建文件留在模板目录，选择另一个模板时清空筛选与选择", async () => {
  const result = await fetchManagedFiles("custom_templates", "", 1);
  vi.mocked(fetchManagedFiles).mockResolvedValue({
    ...result,
    groups: [...result.groups!, { directory: "other", count: 1, size_bytes: 8 }],
  });
  render(
    <>
      <ManagedFilesPanel />
    </>,
  );
  await screen.findByText("管理");
  await act(async () => {
    fireEvent.click(screen.getByText("管理"));
  });
  await selectTemplate();
  await act(async () => {
    fireEvent.click(screen.getByText("新建源码"));
  });
  const editor = await modalLayer("上传或新建文件");
  expect(within(editor).getByText("demo/")).toBeInTheDocument();
  fireEvent.change(within(editor).getByLabelText("文件相对路径"), {
    target: { value: "helper.typ" },
  });
  await act(async () => {
    fireEvent.click(within(editor).getByText(/保.?存/));
  });
  await waitFor(() =>
    expect(mutateManagedFile).toHaveBeenCalledWith(
      expect.objectContaining({
        partition: "custom_templates",
        name: "demo/helper.typ",
        operation: "create",
      }),
    ),
  );
  await waitFor(() => expect(editor).not.toBeVisible());
  await act(async () => {
    fireEvent.click(screen.getByText("Typst 模板（.typ）"));
  });
  const fileRow = screen.getByText("report.typ", { exact: true }).closest("tr")!;
  await waitFor(() => expect(within(fileRow).getByRole("checkbox")).toBeEnabled());
  await act(async () => {
    fireEvent.click(within(fileRow).getByRole("checkbox"));
  });
  expect(screen.getByText("已选 1 项（最多 200，支持跨页）")).toBeInTheDocument();
  await selectTemplate("other");
  expect(screen.getByText("全部类型").closest("button")).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByText("已选 0 项（最多 200，支持跨页）")).toBeInTheDocument();
  await waitFor(() =>
    expect(fetchManagedFiles).toHaveBeenLastCalledWith("custom_templates", "", 1, "", "other"),
  );
}, 20000);

it("手动模板与缺少入口的目录都提供整组移除，不要求安装标记", async () => {
  vi.mocked(fetchReportTemplates).mockResolvedValue([
    {
      id: "demo",
      label: "我的模板",
      display_name: "我的模板",
      is_custom: true,
      has_typst: true,
      can_uninstall: false,
    },
  ]);
  vi.mocked(uninstallTemplate).mockResolvedValue({ name: "demo", removed: true });
  render(
    <>
      <ManagedFilesPanel />
    </>,
  );
  await screen.findByText("管理");
  await act(async () => {
    fireEvent.click(screen.getByText("管理"));
  });
  await selectTemplate();
  await act(async () => {
    fireEvent.click(screen.getByText("移除模板"));
  });
  expect(await screen.findByText(/包括当前筛选未显示的文件/)).toBeInTheDocument();
  await act(async () => {
    fireEvent.click(screen.getByText("移除整个模板"));
  });
  await waitFor(() => expect(uninstallTemplate).toHaveBeenCalledWith("demo"));
  await waitFor(() => expect(screen.queryByText("移除模板")).toBeNull());
  vi.mocked(fetchReportTemplates).mockResolvedValue([]);
  await act(async () => {
    fireEvent.click(screen.getByText("刷新模板"));
  });
  await waitFor(() => expect(fetchReportTemplates).toHaveLastResolvedWith([]));
  await selectTemplate("demo");
  expect(
    await screen.findByText("此目录缺少有效的渲染入口，仍可维护文件或整组移除。"),
  ).toBeInTheDocument();
  expect(screen.getByText("移除模板")).toBeInTheDocument();
}, 20000);

it("从分区跳转业务页面时关闭抽屉，避免遮住目标页面", async () => {
  const partition = (await fetchManagedPartitions())[0];
  vi.mocked(fetchManagedPartitions).mockResolvedValue([
    { ...partition, key: "reports", name: "历史报告文件", writable: false },
  ]);
  const navigate = vi.fn();
  render(
    <>
      <ManagedFilesPanel onNavigate={navigate} />
    </>,
  );
  await screen.findByText("管理");
  await act(async () => {
    fireEvent.click(screen.getByText("管理"));
  });
  await act(async () => {
    fireEvent.click(screen.getByText("打开历史报告预览与重绘"));
  });
  expect(navigate).toHaveBeenCalledWith("reports");
  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: "历史报告文件" })).not.toBeInTheDocument(),
  );
});

it("大量模板通过虚拟下拉列表搜索选择，不把所有模板铺到页面", async () => {
  const select = vi.fn();
  const groups = Array.from({ length: 500 }, (_, index) => ({
    directory: `theme_${index}`,
    count: 2,
    size_bytes: 20,
  }));
  render(
    <>
      <TemplatePackages
        groups={groups}
        directory=""
        loading={false}
        busy={false}
        onSelect={select}
        onInstall={vi.fn()}
        onCreate={vi.fn()}
        onRefresh={vi.fn()}
      />
    </>,
  );
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /^选择自定义模板：/ }));
  });
  expect(screen.getAllByRole("option").length).toBeLessThan(30);
  const input = screen.getByRole("combobox", { name: "搜索选择自定义模板" });
  fireEvent.change(input, { target: { value: "theme_499" } });
  await screen.findByRole("option", { name: "theme_499" });
  await act(async () => {
    fireEvent.click(screen.getByRole("option", { name: "theme_499" }));
  });
  expect(select).toHaveBeenCalledWith("theme_499");
});

it("嵌套详情的 Escape 只关闭当前窗口，最终返回分区管理入口", async () => {
  render(<ManagedFilesPanel />);
  const trigger = await screen.findByRole("button", { name: "管理" });
  trigger.focus();
  await act(async () => {
    fireEvent.click(trigger);
  });
  await selectTemplate();
  const fileButton = await screen.findByRole("button", { name: "查看 / 编辑" });
  fileButton.focus();
  await act(async () => {
    fireEvent.click(fileButton);
  });
  const detail = await modalLayer("demo/report.typ");
  await act(async () => {
    fireEvent.keyDown(detail, { key: "Escape" });
  });
  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: "demo/report.typ" })).not.toBeInTheDocument(),
  );
  expect(fileButton).toHaveFocus();
  const parent = screen.getByRole("dialog", { name: "自定义报告模板" });
  expect(within(parent).getByRole("button", { name: "关闭分区" })).toBeVisible();
  await act(async () => {
    fireEvent.keyDown(parent, { key: "Escape" });
  });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(trigger).toHaveFocus();
});
