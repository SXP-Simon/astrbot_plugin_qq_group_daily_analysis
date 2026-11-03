import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ConfigProvider } from "antd";
import { ManagedFilesPanel } from "../ManagedFilesPanel";
import { fetchManagedContent, fetchManagedFiles, fetchManagedPartitions } from "../../../../../entities/plugin-data/api/managedFilesApi";

vi.mock("../../../../../entities/plugin-data/api/managedFilesApi", () => ({
  fetchManagedContent: vi.fn(), fetchManagedFiles: vi.fn(), fetchManagedPartitions: vi.fn(), mutateManagedFile: vi.fn(), deleteManagedFiles: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(fetchManagedPartitions).mockResolvedValue([{ key: "custom_templates", name: "自定义报告模板", directory: "/data/templates", description: "模板源码", impact: "后续渲染生效", count: 1, size_bytes: 5, writable: true, deletable: true }]);
  vi.mocked(fetchManagedFiles).mockResolvedValue({ items: [{ name: "demo/report.typ", size_bytes: 5, modified_at: 1, media_type: "text/plain", editable: true, downloadable: true, revision: "stat:original" }], total: 1 });
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
  fireEvent.click(await screen.findByText("新建源码"));
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
