import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TemplateResources } from "../TemplateResources";
import { ResourceManagementContext } from "../../model/ResourceManagementContext";
import {
  fetchTemplateResources,
  downloadTemplateResource,
} from "../../../../entities/config/api/templateResourceApi";

vi.mock("../../../../entities/config/api/templateResourceApi", () => ({
  fetchTemplateResources: vi.fn(),
  downloadTemplateResource: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("素材管理入口携带主题和当前 CDN，按文件上传自动使用清单路径", async () => {
  vi.mocked(fetchTemplateResources).mockResolvedValue({
    directory: "/data/resources",
    groups: [
      { theme: "HatsuneMiku", files: [{ name: "HatsuneMiku/icon.svg", available: false }] },
      { theme: "ATRI", files: [{ name: "ATRI/paper.png", available: false }] },
    ],
  });
  const open = vi.fn(),
    onUpload = vi.fn();
  const navigation = { open, request: null, handled: vi.fn(), changed: vi.fn(), version: 0 };
  const { rerender } = render(
    <ResourceManagementContext.Provider value={navigation}>
      <TemplateResources cdnBaseUrl="https://cdn.jsdelivr.net" initialTheme="ATRI" />
    </ResourceManagementContext.Provider>,
  );
  await screen.findByText("下载 ATRI 素材");
  fireEvent.click(screen.getByRole("button", { name: "管理 / 上传模板素材" }));
  expect(open).toHaveBeenCalledWith({ theme: "ATRI", cdnBaseUrl: "https://cdn.jsdelivr.net" });
  expect(screen.queryByText("下载 HatsuneMiku 素材")).not.toBeInTheDocument();
  rerender(
    <TemplateResources
      cdnBaseUrl="https://cdn.jsdelivr.net"
      initialTheme="ATRI"
      onUpload={onUpload}
    />,
  );
  await screen.findByText("ATRI/paper.png");
  const file = new File([new Uint8Array(20)], "different-name.png", { type: "image/png" });
  fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [file] } });
  await vi.waitFor(() => expect(onUpload).toHaveBeenCalledWith(expect.any(File), "ATRI/paper.png"));
});

it("非法下载地址保留输入和错误，不触发无内容变更的刷新", async () => {
  vi.mocked(fetchTemplateResources).mockResolvedValue({
    directory: "data/resources",
    groups: [{ theme: "HatsuneMiku", files: [{ name: "HatsuneMiku/icon.svg", available: false }] }],
  });
  const changed = vi.fn();
  render(<TemplateResources cdnBaseUrl="https://cdn.example.test" onChanged={changed} />);
  await screen.findByText("下载 HatsuneMiku 素材");
  fireEvent.change(screen.getByLabelText("素材下载 CDN"), {
    target: { value: "https://example.test/wrong/path" },
  });
  fireEvent.click(screen.getByRole("button", { name: "下载全部缺失素材" }));
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(screen.getByLabelText("素材下载 CDN")).toHaveValue("https://example.test/wrong/path");
  expect(downloadTemplateResource).not.toHaveBeenCalled();
  expect(changed).not.toHaveBeenCalled();
});

it("完成真实缺图补齐后通知管理页，重复选择同一上传文件仍按清单路径处理", async () => {
  vi.mocked(fetchTemplateResources).mockResolvedValue({
    directory: "data/resources",
    groups: [{ theme: "ATRI", files: [{ name: "ATRI/paper.png", available: false }] }],
  });
  vi.mocked(downloadTemplateResource).mockResolvedValue({
    name: "ATRI/paper.png",
    available: true,
  });
  const changed = vi.fn(),
    upload = vi.fn();
  render(
    <TemplateResources
      cdnBaseUrl="https://cdn.example.test"
      initialTheme="ATRI"
      onChanged={changed}
      onUpload={upload}
    />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "下载 ATRI 素材" }));
  expect(await screen.findByText("本轮素材下载完成")).toBeVisible();
  expect(changed).toHaveBeenCalledOnce();
  expect(screen.getByRole("progressbar", { name: "模板素材处理进度" })).toHaveAttribute(
    "aria-valuenow",
    "100",
  );
  const input = screen.getByLabelText("上传或替换 ATRI/paper.png");
  const file = new File(["image"], "mine.png", { type: "image/png" });
  fireEvent.change(input, { target: { files: [file] } });
  fireEvent.change(input, { target: { files: [file] } });
  expect(upload).toHaveBeenCalledTimes(2);
  expect(upload).toHaveBeenLastCalledWith(file, "ATRI/paper.png");
});
