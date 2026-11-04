import { apiPost, extractData } from "../../../shared/api/bridge";

/** 单次页面队列的请求所有权；取消必须由后端确认，不能只中断页面等待。 */
export class DownloadBatch {
  stopped = false;
  private active = new Set<string>();

  async run<T>(download: (id: string) => Promise<T>): Promise<T> {
    // getRandomValues 在普通 HTTP 的宿主 WebUI 也可用，randomUUID 需要安全上下文。
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
    const id = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    this.active.add(id);
    try { return await download(id); }
    finally { this.active.delete(id); }
  }

  async cancel(): Promise<void> {
    this.stopped = true;
    const results = await Promise.allSettled([...this.active].map(async download_id => {
      const response = await apiPost("config/downloads/cancel", { download_id });
      const data = extractData<{ download_id?: string; cancelled?: boolean }>(response);
      if (data?.download_id !== download_id || data.cancelled !== true) throw new Error("未收到取消回执");
    }));
    if (results.some(result => result.status === "rejected")) {
      throw new Error("队列已停止，但部分下载的取消尚未确认，请重试取消或等待当前请求结束。");
    }
  }
}
