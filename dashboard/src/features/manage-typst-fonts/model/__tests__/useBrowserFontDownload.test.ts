import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useBrowserFontDownload } from "../useBrowserFontDownload";

let requests: FontRequest[];
class FontRequest {
  onprogress?: (event: ProgressEvent) => void;
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;
  responseType = "";
  response: Blob | null = null;
  status = 200;
  open = vi.fn();
  send = vi.fn();
  abort = vi.fn(() => this.onabort?.());
  constructor() { requests.push(this); }
}
const font = { name: "example.ttf", download_url: "https://raw.githubusercontent.com/example/font.ttf", upstream_url: "https://github.com/example/fonts", cdn_path: null };
let save: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  requests = [];
  vi.stubGlobal("XMLHttpRequest", FontRequest);
  vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:font"), revokeObjectURL: vi.fn() });
  save = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

it("按实际字节反馈进度，下载为预设文件名，不弹窗也不重复发起", () => {
  vi.useFakeTimers();
  const { result } = renderHook(useBrowserFontDownload);
  act(() => { result.current.download(font); result.current.download(font); });
  expect(requests).toHaveLength(1);
  expect(requests[0].open).toHaveBeenCalledWith("GET", font.download_url);
  expect(requests[0].responseType).toBe("blob");
  expect(result.current.transfer?.phase).toBe("connecting");
  act(() => {
    requests[0].onprogress?.(new ProgressEvent("progress", { loaded: 256, total: 1024, lengthComputable: true }));
    vi.advanceTimersByTime(1100);
  });
  expect(result.current.transfer).toMatchObject({ phase: "downloading", received: 256, total: 1024 });
  expect(result.current.elapsed).toBe(1);
  let filename = "";
  let target = "";
  save.mockImplementation(function (this: HTMLAnchorElement) { filename = this.download; target = this.target; });
  const blob = new Blob([new Uint8Array(1024)], { type: "font/ttf" });
  act(() => { requests[0].response = blob; requests[0].onload?.(); });
  expect(result.current.transfer).toMatchObject({ phase: "saved", received: 1024, total: 1024 });
  expect(result.current.running).toBe(false);
  expect(filename).toBe(font.name);
  expect(target).toBe("");
  act(() => vi.runOnlyPendingTimers());
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:font");
});

it("来源没有总大小时保留未知状态，取消后迟到响应不保存文件，可重试", () => {
  const { result } = renderHook(useBrowserFontDownload);
  act(() => result.current.download(font));
  act(() => requests[0].onprogress?.(new ProgressEvent("progress", { loaded: 512 })));
  expect(result.current.transfer).toMatchObject({ received: 512, total: null });
  act(() => result.current.cancel());
  expect(result.current.transfer?.phase).toBe("cancelled");
  act(() => { requests[0].response = new Blob(["late"]); requests[0].onload?.(); });
  expect(save).not.toHaveBeenCalled();
  act(() => result.current.download(font));
  expect(requests).toHaveLength(2);
});

it.each(["http", "network", "empty", "oversized"])("%s 失败时保留来源地址且不保存伪文件", cause => {
  const { result } = renderHook(useBrowserFontDownload);
  act(() => result.current.download(font));
  act(() => {
    if (cause === "network") requests[0].onerror?.();
    else if (cause === "oversized") requests[0].onprogress?.(new ProgressEvent("progress", { loaded: 33 * 1024 * 1024 }));
    else { requests[0].status = cause === "http" ? 404 : 200; requests[0].response = new Blob(); requests[0].onload?.(); }
  });
  expect(result.current.transfer).toMatchObject({ phase: "failed", font });
  expect(result.current.transfer?.error).toBeTruthy();
  expect(save).not.toHaveBeenCalled();
  expect(result.current.running).toBe(false);
});

it("关闭字体管理后终止请求，迟到响应不触发保存", () => {
  const { result, unmount } = renderHook(useBrowserFontDownload);
  act(() => result.current.download(font));
  unmount();
  expect(requests[0].abort).toHaveBeenCalledOnce();
  requests[0].response = new Blob(["late"]);
  requests[0].onload?.();
  expect(save).not.toHaveBeenCalled();
});
