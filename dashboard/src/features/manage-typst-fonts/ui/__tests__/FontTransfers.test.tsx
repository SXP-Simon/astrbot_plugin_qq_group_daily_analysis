import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { FontDownloadProgress } from "@/features/manage-typst-fonts/ui/FontDownloadProgress";
import { FontUploadProgress } from "@/features/manage-typst-fonts/ui/FontUploadProgress";
import { BrowserFontDownloadProgress } from "@/features/manage-typst-fonts/ui/BrowserFontDownloadProgress";
import type { useFontDownload } from "@/features/manage-typst-fonts/model/useFontDownload";
import type { useFontUpload } from "@/features/manage-typst-fonts/model/useFontUpload";
import type { useBrowserFontDownload } from "@/features/manage-typst-fonts/model/useBrowserFontDownload";
it("字体下载显示真实字节、来源、超时提示和取消入口，失败清单继续可读", () => {
  const download: ReturnType<typeof useFontDownload> = {
    progress: { done: 1, total: 3, current: "font.ttf", failed: [] },
    running: true,
    error: "",
    cancelled: false,
    cancelling: false,
    cancel: vi.fn(async () => {}),
    download: vi.fn(async () => {}),
    source: "cdn",
    setSource: vi.fn(),
    fallbacks: ["font.ttf"],
    progressError: "",
    transfer: {
      name: "font.ttf",
      url: "https://example.test/font.ttf",
      phase: "downloading",
      received: 1048576,
      total: 5242880,
      elapsed_seconds: 12,
      idle_seconds: 7,
    },
  };
  const view = render(<FontDownloadProgress download={download} />);
  expect(screen.getByRole("progressbar", { name: "当前字体下载进度" })).toHaveAttribute(
    "aria-valuenow",
    "20",
  );
  expect(screen.getByText(/1.0 MB.*5.0 MB/)).toBeVisible();
  expect(screen.getByText(/已 7 秒未收到新数据/)).toBeVisible();
  expect(screen.getByText(/https:\/\/example.test\/font.ttf/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "取消下载" }));
  expect(download.cancel).toHaveBeenCalledOnce();
  view.rerender(
    <FontDownloadProgress
      download={{
        ...download,
        running: false,
        transfer: null,
        progress: {
          ...download.progress,
          done: 3,
          failed: [{ name: "bad.ttf", message: "网络超时" }],
        },
      }}
    />,
  );
  expect(screen.getByRole("list", { name: "未完成的字体" })).toHaveTextContent("bad.ttf：网络超时");
});
it("上传总大小未知时不伪造进度，失败和已保存明确区分", () => {
  const upload: ReturnType<typeof useFontUpload> = {
    progress: { name: "font.ttf", received: 0, total: 0, phase: "uploading" },
    running: true,
    elapsed: 2,
    cancelling: false,
    upload: vi.fn(async () => true),
    cancel: vi.fn(async () => {}),
  };
  const view = render(<FontUploadProgress upload={upload} />);
  expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
  fireEvent.click(screen.getByRole("button", { name: "取消上传" }));
  expect(upload.cancel).toHaveBeenCalledOnce();
  view.rerender(
    <FontUploadProgress
      upload={{
        ...upload,
        running: false,
        progress: {
          name: "font.ttf",
          received: 50,
          total: 100,
          phase: "failed",
          error: "字体格式不正确",
        },
      }}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("字体格式不正确");
  view.rerender(
    <FontUploadProgress
      upload={{
        ...upload,
        running: false,
        progress: { name: "font.ttf", received: 100, total: 100, phase: "saved" },
      }}
    />,
  );
  expect(screen.getByText("字体已上传并保存，列表正在刷新。")).toBeVisible();
});
it("浏览器下载保留取消和复制地址，保存到电脑不误称已安装到插件", () => {
  const download: ReturnType<typeof useBrowserFontDownload> = {
    transfer: {
      font: {
        name: "font.ttf",
        download_url: "https://example.test/font.ttf",
        upstream_url: "https://example.test",
        cdn_path: null,
      },
      phase: "downloading",
      received: 50,
      total: null,
    },
    elapsed: 3,
    running: true,
    download: vi.fn(),
    cancel: vi.fn(),
  };
  const view = render(<BrowserFontDownloadProgress download={download} />);
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制字体下载地址" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "取消浏览器下载" }));
  expect(download.cancel).toHaveBeenCalledOnce();
  view.rerender(
    <BrowserFontDownloadProgress
      download={{
        ...download,
        running: false,
        transfer: { ...download.transfer!, phase: "saved", received: 100, total: 100 },
      }}
    />,
  );
  expect(screen.getByText(/才会安装到插件服务器/)).toBeVisible();
});
