import type { FontTransfer } from "@/entities/config/model/typstFonts";

/** 演示真实接口的连接、字节增长与完成清理，不访问网络。 */
export const mockFontDownloads = new Map<
  string,
  { name: string; source: string; started: number }
>();

export function mockFontDownloadProgress(id: string): FontTransfer | null {
  const file = mockFontDownloads.get(id);
  if (!file) return null;
  const elapsed = (Date.now() - file.started) / 1000;
  const total = file.name.startsWith("LXGW") ? 25 * 1024 * 1024 : 2 * 1024 * 1024;
  return {
    name: file.name,
    url: `演示：${file.source === "github" || file.name.startsWith("LXGW") ? "GitHub Raw 直连" : "所选 CDN"}（连接插件后显示实际地址）`,
    received: elapsed < 0.3 ? 0 : Math.min(total, Math.floor((total * elapsed) / 1.5)),
    total,
    phase: elapsed < 0.3 ? "connecting" : "downloading",
    elapsed_seconds: elapsed,
    idle_seconds: 0,
  };
}
