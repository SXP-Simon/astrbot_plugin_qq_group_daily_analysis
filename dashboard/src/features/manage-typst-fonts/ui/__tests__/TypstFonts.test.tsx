import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { TypstFonts } from "../TypstFonts";
import { downloadTypstFonts, fetchTypstFonts } from "../../../../entities/config/api/configApi";
import { mockTypstFonts } from "../../../../mocks/data/templateResources";
import { mockHandlers } from "../../../../mocks/handlers";

vi.mock("../../../../entities/config/api/configApi", () => ({ downloadTypstFonts: vi.fn(), fetchTypstFonts: vi.fn() }));
const initial = structuredClone(mockTypstFonts);

beforeEach(() => {
  vi.resetAllMocks();
  Object.assign(mockTypstFonts, structuredClone(initial));
  vi.mocked(fetchTypstFonts).mockImplementation(async () => structuredClone(mockTypstFonts));
  vi.mocked(downloadTypstFonts).mockImplementation(async (_cdn, theme, name) => {
    mockHandlers["POST config/typst-fonts/download"]({ theme, name });
    return structuredClone(mockTypstFonts);
  });
});

it("仅下载所选模板，其他模板字体仍可继续按需或全部下载", async () => {
  render(<TypstFonts cdnBaseUrl="https://cdn.jsdelivr.net" />);
  expect(await screen.findByText("所选模板还需下载 6 / 8 个字体文件")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "下载所选模板字体" }));
  expect(await screen.findByText("所选模板字体已就绪")).toBeVisible();
  expect(downloadTypstFonts).toHaveBeenCalledWith("https://cdn.jsdelivr.net", "HatsuneMiku", expect.any(String), expect.any(String));
  expect(mockTypstFonts.ready).toBe(false);
  expect(mockTypstFonts.missing).toContain("Cinzel.ttf");
  await waitFor(() => expect(screen.getByRole("button", { name: "下载全部预设字体" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "下载全部预设字体" }));
  await waitFor(() => expect(mockTypstFonts.ready).toBe(true));
  expect(downloadTypstFonts).toHaveBeenLastCalledWith("https://cdn.jsdelivr.net", undefined, expect.any(String), expect.any(String));
}, 15000);

it("下载中断后刷新已完成的文件状态并保留可读错误", async () => {
  vi.mocked(downloadTypstFonts).mockImplementation(async () => {
    mockTypstFonts.files.push("NotoSansJP.ttf");
    mockTypstFonts.groups?.forEach(group => { group.missing = group.missing.filter(file => file !== "NotoSansJP.ttf"); });
    throw new Error("CDN 下载中断，请切换 CDN 后重试");
  });
  render(<TypstFonts cdnBaseUrl="https://cdn.jsdelivr.net" />);
  await screen.findByText("所选模板还需下载 6 / 8 个字体文件");
  fireEvent.click(screen.getByRole("button", { name: "下载所选模板字体" }));
  expect(await screen.findByText("所选模板还需下载 5 / 8 个字体文件")).toBeVisible();
  expect(screen.getAllByText(/CDN 下载中断，请切换 CDN 后重试/).length).toBeGreaterThan(0);
}, 15000);


it("可从字体进度取消当前文件且不启动后续字体", async () => {
  let rejectDownload: ((error: Error) => void) | undefined;
  let activeId = "";
  vi.mocked(downloadTypstFonts).mockImplementation((_cdn, _theme, _name, id) => {
    activeId = id!;
    return new Promise((_resolve, reject) => { rejectDownload = reject; });
  });
  const bridge = await import("../../../../shared/api/bridge");
  const cancelApi = vi.spyOn(bridge, "apiPost").mockImplementation(async (_path, body) => {
    expect(body).toEqual({ download_id: activeId });
    rejectDownload?.(new Error("下载已取消"));
    return { status: "ok", data: { download_id: activeId, cancelled: true } };
  });
  render(<TypstFonts cdnBaseUrl="https://cdn.jsdelivr.net" />);
  await screen.findByText("所选模板还需下载 6 / 8 个字体文件");
  fireEvent.click(screen.getByRole("button", { name: "下载所选模板字体" }));
  fireEvent.click(await screen.findByRole("button", { name: "取消下载" }));
  await act(async () => { await Promise.resolve(); });
  expect(await screen.findByText(/下载已取消，已完成的字体会保留/)).toBeVisible();
  expect(downloadTypstFonts).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/字体处理 0\/6，成功 0，失败 0/)).toBeVisible();
  cancelApi.mockRestore();
});
