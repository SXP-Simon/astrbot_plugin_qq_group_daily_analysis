import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ConfigProvider } from "antd";
import { ManagedFilesPanel } from "../ManagedFilesPanel";
import { fetchManagedContent, fetchManagedFiles, fetchManagedPartitions, mutateManagedFile } from "../../../../../entities/plugin-data/api/managedFilesApi";
import { fetchReportTemplates } from "../../../../../entities/report/api/reportApi";

vi.mock("../../../../../entities/plugin-data/api/managedFilesApi", () => ({
  fetchManagedContent: vi.fn(), fetchManagedFiles: vi.fn(), fetchManagedPartitions: vi.fn(), mutateManagedFile: vi.fn(), deleteManagedFiles: vi.fn(),
}));
vi.mock("../../../../../entities/report/api/reportApi", () => ({ fetchReportTemplates: vi.fn(), uninstallTemplate: vi.fn() }));

beforeEach(() => {
  vi.mocked(fetchManagedPartitions).mockResolvedValue([{ key: "custom_templates", name: "自定义报告模板", directory: "/data/templates", description: "模板源码", impact: "后续渲染生效", count: 1, size_bytes: 5, writable: true, deletable: true }]);
  vi.mocked(fetchManagedFiles).mockResolvedValue({ items: [{ name: "demo/report.typ", size_bytes: 5, modified_at: 1, media_type: "text/plain", editable: true, downloadable: true, revision: "stat:original" }], total: 1, groups: [{ directory: "demo", count: 3, size_bytes: 20 }] });
  vi.mocked(fetchReportTemplates).mockResolvedValue([{ id: "demo", label: "我的模板", display_name: "我的模板", is_custom: true, has_typst: true, can_uninstall: true }]);
  vi.mocked(fetchManagedContent).mockResolvedValue({ name: "demo/report.typ", text: "Hello", content_base64: "SGVsbG8=", media_type: "text/plain", revision: "original" });
  const computedStyle = window.getComputedStyle.bind(window);
  vi.spyOn(window, "getComputedStyle").mockImplementation(element => computedStyle(element));
  vi.stubGlobal("URL", class extends URL { static createObjectURL() { return "blob:preview"; } static revokeObjectURL() {} });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

async function modalLayer(title: string) {
  const heading = await screen.findByText(title, { selector: ".ant-modal-title" });
  return heading.closest<HTMLElement>(".ant-modal-wrap")!;
}

it("详情与子编辑弹窗继承父层级，关闭编辑后仍可查看详情", async () => {
  render(<ConfigProvider theme={{ token: { motion: false, zIndexPopupBase: 1500 } }}><ManagedFilesPanel /></ConfigProvider>);
  fireEvent.click(await screen.findByText("管理"));
  fireEvent.click(await screen.findByText("管理文件"));
  fireEvent.click(await screen.findByText("查看 / 编辑"));
  const detail = await modalLayer("demo/report.typ");
  const drawer = document.querySelector<HTMLElement>(".ant-drawer")!;
  const detailLayer = Number(getComputedStyle(detail).zIndex);
  expect(detailLayer).toBeGreaterThan(Number(getComputedStyle(drawer).zIndex));
  fireEvent.click(within(detail).getByText("编辑源码"));
  const editor = await modalLayer("替换或编辑文件");
  expect(Number(getComputedStyle(editor).zIndex)).toBeGreaterThan(detailLayer);
  fireEvent.click(within(editor).getByText(/取.?消/));
  await waitFor(() => expect(editor).not.toBeVisible());
  expect(detail).toBeVisible();
  fireEvent.click(within(detail).getByText("重命名"));
  const rename = await modalLayer("重命名文件");
  expect(Number(getComputedStyle(rename).zIndex)).toBeGreaterThan(detailLayer);
}, 20000);

it("从抽屉新建源码与安装模板时，弹窗显示在抽屉上方", async () => {
  render(<ConfigProvider theme={{ token: { motion: false } }}><ManagedFilesPanel /></ConfigProvider>);
  fireEvent.click(await screen.findByText("管理"));
  fireEvent.click(await screen.findByText("新建模板源码"));
  const editor = await modalLayer("上传或新建文件");
  const drawer = document.querySelector<HTMLElement>(".ant-drawer")!;
  const drawerLayer = Number(getComputedStyle(drawer).zIndex);
  expect(Number(getComputedStyle(editor).zIndex)).toBeGreaterThan(drawerLayer);
  fireEvent.click(within(editor).getByText(/取.?消/));
  fireEvent.click(screen.getByText("安装模板包"));
  const installTitle = await screen.findByText("安装自定义报告模板");
  const install = installTitle.closest(".ant-modal-wrap")!;
  expect(Number(getComputedStyle(install).zIndex)).toBeGreaterThan(drawerLayer);
}, 20000);

it("模板类型直接可见且筛选传给接口，报告区只提供相关类型", async () => {
  const template = (await fetchManagedPartitions())[0];
  vi.mocked(fetchManagedPartitions).mockResolvedValue([template, { ...template, key: "reports", name: "历史报告文件", writable: false }]);
  render(<ConfigProvider theme={{ token: { motion: false } }}><ManagedFilesPanel /></ConfigProvider>);
  fireEvent.click(within((await screen.findByText("自定义报告模板")).closest("tr")!).getByText("管理"));
  expect(await screen.findByText("我的模板")).toBeVisible();
  expect(screen.getByText("3 个文件 · 20 B")).toBeVisible();
  fireEvent.click(await screen.findByText("管理文件"));
  const filters = document.querySelector<HTMLElement>('[role="group"][aria-label="文件类型筛选"]')!;
  const typ = within(filters).getByText("Typst 模板（.typ）").closest("button")!;
  expect(typ).toBeVisible();
  fireEvent.click(typ);
  await waitFor(() => expect(fetchManagedFiles).toHaveBeenLastCalledWith("custom_templates", "", 1, "typ", "demo"));
  expect(typ).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByLabelText("Close"));
  fireEvent.click(within(screen.getByText("历史报告文件").closest("tr")!).getByText("管理"));
  const reportFilters = document.querySelector<HTMLElement>('[role="group"][aria-label="文件类型筛选"]')!;
  expect(within(reportFilters).queryByText(/Typst/)).toBeNull();
  fireEvent.click(within(reportFilters).getByText("JPG + PNG"));
  await waitFor(() => expect(fetchManagedFiles).toHaveBeenLastCalledWith("reports", "", 1, "jpg,jpeg,png", ""));
}, 20000);

it("包内新建文件默认留在模板目录，返回列表后清空筛选与选择", async () => {
  render(<ConfigProvider theme={{ token: { motion: false } }}><ManagedFilesPanel /></ConfigProvider>);
  fireEvent.click(await screen.findByText("管理"));
  fireEvent.click(await screen.findByText("管理文件"));
  fireEvent.click(screen.getByText("新建源码"));
  const editor = await modalLayer("上传或新建文件");
  expect(within(editor).getByText("demo/")).toBeInTheDocument();
  fireEvent.change(within(editor).getByLabelText("文件相对路径"), { target: { value: "helper.typ" } });
  fireEvent.click(within(editor).getByText(/保.?存/));
  await waitFor(() => expect(mutateManagedFile).toHaveBeenCalledWith(expect.objectContaining({ partition: "custom_templates", name: "demo/helper.typ", operation: "create" })));
  await waitFor(() => expect(editor).not.toBeVisible());
  fireEvent.click(screen.getByText("Typst 模板（.typ）"));
  fireEvent.click(screen.getByText("返回模板列表"));
  expect(await screen.findByText("我的模板")).toBeVisible();
  fireEvent.click(screen.getByText("管理文件"));
  expect(screen.getByText("全部类型").closest("button")).toHaveAttribute("aria-pressed", "true");
}, 20000);

it("从分区跳转业务页面时关闭抽屉，避免遮住目标页面", async () => {
  const partition = (await fetchManagedPartitions())[0];
  vi.mocked(fetchManagedPartitions).mockResolvedValue([{ ...partition, key: "reports", name: "历史报告文件", writable: false }]);
  const navigate = vi.fn();
  render(<ConfigProvider theme={{ token: { motion: false } }}><ManagedFilesPanel onNavigate={navigate} /></ConfigProvider>);
  fireEvent.click(await screen.findByText("管理"));
  fireEvent.click(screen.getByText("打开历史报告预览与重绘"));
  expect(navigate).toHaveBeenCalledWith("reports");
  await waitFor(() => expect(document.querySelector(".ant-drawer-open")).toBeNull());
});
