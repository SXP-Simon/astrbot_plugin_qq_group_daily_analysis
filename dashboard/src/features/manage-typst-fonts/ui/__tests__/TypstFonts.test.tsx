import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  vi.mocked(downloadTypstFonts).mockImplementation(async (_cdn, theme) => {
    mockHandlers["POST config/typst-fonts/download"]({ theme });
    return structuredClone(mockTypstFonts);
  });
});

it("仅下载所选模板，其他模板字体仍可继续按需或全部下载", async () => {
  render(<TypstFonts cdnBaseUrl="https://cdn.jsdelivr.net" />);
  expect(await screen.findByText("所选模板还需下载 6 / 8 个字体文件")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "下载所选模板字体" }));
  expect(await screen.findByText("所选模板字体已就绪")).toBeVisible();
  expect(downloadTypstFonts).toHaveBeenCalledWith("https://cdn.jsdelivr.net", "HatsuneMiku");
  expect(mockTypstFonts.ready).toBe(false);
  expect(mockTypstFonts.missing).toContain("Cinzel.ttf");
  await waitFor(() => expect(screen.getByRole("button", { name: "下载全部预设字体" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "下载全部预设字体" }));
  await waitFor(() => expect(mockTypstFonts.ready).toBe(true));
  expect(downloadTypstFonts).toHaveBeenLastCalledWith("https://cdn.jsdelivr.net", undefined);
});

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
  expect(screen.getByText("CDN 下载中断，请切换 CDN 后重试")).toBeVisible();
});
