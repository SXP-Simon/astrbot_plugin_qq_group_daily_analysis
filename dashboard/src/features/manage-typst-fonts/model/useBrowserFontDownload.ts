import { useEffect, useRef, useState } from "react";
import type { TypstFontPreset } from "../../../entities/config/model/typstFonts";

interface BrowserFontTransfer {
  font: TypstFontPreset;
  phase: "connecting" | "downloading" | "saved" | "failed" | "cancelled";
  received: number;
  total: number | null;
  error?: string;
}

/** 在浏览器接收并保存字体，不依赖弹窗或插件服务器的网络。 */
export function useBrowserFontDownload() {
  const [transfer, setTransfer] = useState<BrowserFontTransfer | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const request = useRef<XMLHttpRequest | null>(null);
  const running = transfer?.phase === "connecting" || transfer?.phase === "downloading";

  useEffect(() => () => {
    const active = request.current;
    request.current = null;
    active?.abort();
  }, []);
  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [running]);

  const download = (font: TypstFontPreset) => {
    if (request.current) return;
    const xhr = new XMLHttpRequest();
    request.current = xhr;
    setElapsed(0);
    setTransfer({ font, phase: "connecting", received: 0, total: null });
    const fail = (error: string) => {
      if (request.current !== xhr) return;
      setTransfer(value => value && ({ ...value, phase: "failed", error }));
      request.current = null;
      xhr.abort();
    };
    xhr.onprogress = event => {
      if (request.current !== xhr) return;
      // 与字体上传的 32 MiB 限制一致，避免下载无法上传的大文件。
      if (event.loaded > 32 * 1024 * 1024 || event.total > 32 * 1024 * 1024) {
        fail("字体超过 32 MiB，已停止接收；请核对来源与字体版本。");
        return;
      }
      setTransfer({ font, phase: "downloading", received: event.loaded, total: event.lengthComputable && event.total > 0 ? event.total : null });
    };
    xhr.onload = () => {
      if (request.current !== xhr) return;
      if (xhr.status < 200 || xhr.status >= 300) { fail(`来源返回 HTTP ${xhr.status}，请复制下载地址在浏览器中检查。`); return; }
      const blob: unknown = xhr.response;
      if (!(blob instanceof Blob) || !blob.size || blob.size > 32 * 1024 * 1024) { fail("来源未返回有效大小的字体文件，请核对下载地址。"); return; }
      let url: string | undefined;
      try {
        url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = font.name;
        document.body.appendChild(anchor);
        try { anchor.click(); } finally { anchor.remove(); }
        setTransfer({ font, phase: "saved", received: blob.size, total: blob.size });
        request.current = null;
      } catch {
        fail("无法交给浏览器保存，请复制下载地址后在新标签页下载。");
      } finally {
        if (url) { const savedUrl = url; setTimeout(() => URL.revokeObjectURL(savedUrl), 0); }
      }
    };
    xhr.onerror = () => fail("浏览器无法读取字体来源，可能是网络、代理或跨域限制；可复制下载地址后在新标签页下载。");
    xhr.onabort = () => {
      if (request.current !== xhr) return;
      request.current = null;
      setTransfer(value => value && ({ ...value, phase: "cancelled" }));
    };
    try {
      xhr.open("GET", font.download_url);
      xhr.responseType = "blob";
      xhr.send();
    } catch {
      fail("无法发起浏览器下载，请复制下载地址后在新标签页下载。");
    }
  };
  return { transfer, elapsed, running, download, cancel: () => request.current?.abort() };
}
