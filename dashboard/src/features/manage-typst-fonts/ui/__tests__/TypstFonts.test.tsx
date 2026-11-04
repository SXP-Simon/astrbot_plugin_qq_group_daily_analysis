import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { TypstFonts } from "../TypstFonts";
import { downloadTypstFonts, fetchTypstFonts, fetchFontDownloadProgress } from "../../../../entities/config/api/configApi";
import { mockTypstFonts } from "../../../../mocks/data/templateResources";
import { mockHandlers } from "../../../../mocks/handlers";
import { FontManagementContext } from "../../model/FontManagementContext";

vi.mock("../../../../entities/config/api/configApi", () => ({ downloadTypstFonts: vi.fn(), fetchTypstFonts: vi.fn(), fetchFontDownloadProgress: vi.fn().mockResolvedValue(null) }));
const initial = structuredClone(mockTypstFonts);

beforeEach(() => {
  vi.resetAllMocks();
  Object.assign(mockTypstFonts, structuredClone(initial));
  vi.mocked(fetchTypstFonts).mockImplementation(async () => structuredClone(mockTypstFonts));
  vi.mocked(fetchFontDownloadProgress).mockResolvedValue(null);
  vi.mocked(downloadTypstFonts).mockImplementation(async (_cdn, theme, name) => {
    mockHandlers["POST config/typst-fonts/download"]({ theme, name });
    return structuredClone(mockTypstFonts);
  });
});

it("管理入口保留模板与来源，管理完成后刷新状态", async () => {
  const open = vi.fn();
  const { rerender } = render(<FontManagementContext.Provider value={{ open, version: 0, changed: vi.fn() }}><TypstFonts cdnBaseUrl="https://cdn.jsdelivr.net" /></FontManagementContext.Provider>);
  await screen.findByText("所选模板还需下载 7 / 9 个字体文件");
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "字体模板" }));
  fireEvent.click(screen.getByText("ATRI (亚托莉)"));
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "字体下载来源" }));
  fireEvent.click(screen.getByText("GitHub Raw 直连（全部字体）"));
  fireEvent.click(screen.getByRole("button", { name: "管理 / 上传字体" }));
  expect(open).toHaveBeenCalledWith({ theme: "ATRI", cdnBaseUrl: "https://cdn.jsdelivr.net", source: "github" });
  const group = mockTypstFonts.groups!.find(item => item.theme === "ATRI")!;
  group.missing = []; group.ready = true;
  rerender(<FontManagementContext.Provider value={{ open, version: 1, changed: vi.fn() }}><TypstFonts cdnBaseUrl="https://cdn.jsdelivr.net" /></FontManagementContext.Provider>);
  expect(await screen.findByText("所选模板字体已就绪")).toBeVisible();
});

it("CDN 失败自动切换 Raw，而固定 Raw 大字库失败只尝试一次", async () => {
  const fonts = structuredClone(initial);
  const names = ["Outfit.ttf", "cjkFonts_allseto_v1.11.ttf"];
  fonts.missing = [...names];
  fonts.groups = [{ theme: "HatsuneMiku", required: names, missing: [...names], ready: false }];
  vi.mocked(fetchTypstFonts).mockImplementation(async () => structuredClone(fonts));
  vi.mocked(downloadTypstFonts).mockImplementation(async (_cdn, _theme, name, _id, source) => {
    if (name !== "Outfit.ttf" || source === "cdn") throw new Error("网络不可用");
    fonts.groups![0].missing = fonts.groups![0].missing.filter(item => item !== name);
    fonts.missing = fonts.missing.filter(item => item !== name);
    return structuredClone(fonts);
  });
  render(<TypstFonts cdnBaseUrl="https://cdn.jsdelivr.net" />);
  await screen.findByText("所选模板还需下载 2 / 2 个字体文件");
  fireEvent.click(screen.getByRole("button", { name: "下载所选模板字体" }));
  expect(await screen.findByText("字体处理 2/2，成功 1，失败 1")).toBeVisible();
  expect(vi.mocked(downloadTypstFonts).mock.calls.map(call => [call[2], call[4]])).toEqual([[names[0], "cdn"], [names[0], "github"], [names[1], "cdn"]]);
  expect(screen.getByText(/已自动改用 GitHub Raw 重试：Outfit.ttf/)).toBeVisible();
});

it("选择 Raw 后传递来源，展示真实字节与等待时间，失败原因不会被覆盖", async () => {
  let rejectDownload: ((error: Error) => void) | undefined;
  vi.mocked(downloadTypstFonts).mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectDownload = reject; }));
  vi.mocked(fetchFontDownloadProgress).mockResolvedValue({
    name: "NotoSansJP.ttf", url: "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP[wght].ttf",
    received: 1048576, total: 5242880, phase: "downloading", elapsed_seconds: 12, idle_seconds: 7,
  });
  render(<TypstFonts cdnBaseUrl="https://cdn.jsdelivr.net" />);
  await screen.findByText("所选模板还需下载 7 / 9 个字体文件");
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "字体下载来源" }));
  fireEvent.click(screen.getByText("GitHub Raw 直连（全部字体）"));
  fireEvent.click(screen.getByRole("button", { name: "下载所选模板字体" }));
  expect(await screen.findByText(/正在接收字体：1\.0 MB \/ 5\.0 MB/)).toBeVisible();
  expect(screen.getByText(/已 7 秒未收到新数据/)).toBeVisible();
  expect(downloadTypstFonts).toHaveBeenCalledWith("", "HatsuneMiku", expect.any(String), expect.any(String), "github");
  await act(async () => rejectDownload?.(new Error("NotoSansJP.ttf：来源返回 HTTP 403")));
  expect(await screen.findByText(/NotoSansJP.ttf：来源返回 HTTP 403/)).toBeVisible();
  await waitFor(() => expect(screen.getByRole("button", { name: "下载全部预设字体" })).toBeEnabled());
}, 15000);

it("仅下载所选模板，其他模板字体仍可继续按需或全部下载", async () => {
  render(<TypstFonts cdnBaseUrl="https://cdn.jsdelivr.net" />);
  expect(await screen.findByText("所选模板还需下载 7 / 9 个字体文件")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "下载所选模板字体" }));
  expect(await screen.findByText("所选模板字体已就绪")).toBeVisible();
  expect(downloadTypstFonts).toHaveBeenCalledWith("https://cdn.jsdelivr.net", "HatsuneMiku", expect.any(String), expect.any(String), "cdn");
  expect(mockTypstFonts.ready).toBe(false);
  expect(mockTypstFonts.missing).toContain("Cinzel.ttf");
  await waitFor(() => expect(screen.getByRole("button", { name: "下载全部预设字体" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "下载全部预设字体" }));
  await waitFor(() => expect(mockTypstFonts.ready).toBe(true));
  expect(downloadTypstFonts).toHaveBeenLastCalledWith("https://cdn.jsdelivr.net", undefined, expect.any(String), expect.any(String), "cdn");
}, 15000);

it("下载中断后刷新已完成的文件状态并保留可读错误", async () => {
  vi.mocked(downloadTypstFonts).mockImplementation(async () => {
    mockTypstFonts.files.push("NotoSansJP.ttf");
    mockTypstFonts.groups?.forEach(group => { group.missing = group.missing.filter(file => file !== "NotoSansJP.ttf"); });
    throw new Error("CDN 下载中断，请切换 CDN 后重试");
  });
  render(<TypstFonts cdnBaseUrl="https://cdn.jsdelivr.net" />);
  await screen.findByText("所选模板还需下载 7 / 9 个字体文件");
  fireEvent.click(screen.getByRole("button", { name: "下载所选模板字体" }));
  expect(await screen.findByText("所选模板还需下载 6 / 9 个字体文件")).toBeVisible();
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
  await screen.findByText("所选模板还需下载 7 / 9 个字体文件");
  fireEvent.click(screen.getByRole("button", { name: "下载所选模板字体" }));
  fireEvent.click(await screen.findByRole("button", { name: "取消下载" }));
  await act(async () => { await Promise.resolve(); });
  expect(await screen.findByText(/下载已取消，已完成的字体会保留/)).toBeVisible();
  expect(downloadTypstFonts).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/字体处理 0\/7，成功 0，失败 0/)).toBeVisible();
  cancelApi.mockRestore();
});
