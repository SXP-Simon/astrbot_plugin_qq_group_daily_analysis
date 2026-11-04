import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TemplateResources } from "../TemplateResources";
import { ResourceManagementContext } from "../../model/ResourceManagementContext";
import { fetchTemplateResources } from "../../../../entities/config/api/templateResourceApi";

vi.mock("../../../../entities/config/api/templateResourceApi", () => ({ fetchTemplateResources: vi.fn(), downloadTemplateResource: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("素材管理入口携带主题和当前 CDN，按文件上传自动使用清单路径", async () => {
  vi.mocked(fetchTemplateResources).mockResolvedValue({ directory: "/data/resources", groups: [{ theme: "HatsuneMiku", files: [{ name: "HatsuneMiku/icon.svg", available: false }] }, { theme: "ATRI", files: [{ name: "ATRI/paper.png", available: false }] }] });
  const open = vi.fn(), onUpload = vi.fn();
  const navigation = { open, request: null, handled: vi.fn(), changed: vi.fn(), version: 0 };
  const { rerender } = render(<ResourceManagementContext.Provider value={navigation}><TemplateResources cdnBaseUrl="https://cdn.jsdelivr.net" initialTheme="ATRI" /></ResourceManagementContext.Provider>);
  await screen.findByText("下载 ATRI 素材");
  fireEvent.click(screen.getByRole("button", { name: "管理 / 上传模板素材" }));
  expect(open).toHaveBeenCalledWith({ theme: "ATRI", cdnBaseUrl: "https://cdn.jsdelivr.net" });
  expect(screen.queryByText("下载 HatsuneMiku 素材")).not.toBeInTheDocument();
  rerender(<TemplateResources cdnBaseUrl="https://cdn.jsdelivr.net" initialTheme="ATRI" onUpload={onUpload} />);
  await screen.findByText("ATRI/paper.png");
  const file = new File([new Uint8Array(20)], "different-name.png", { type: "image/png" });
  fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [file] } });
  await vi.waitFor(() => expect(onUpload).toHaveBeenCalledWith(expect.any(File), "ATRI/paper.png"));
});
