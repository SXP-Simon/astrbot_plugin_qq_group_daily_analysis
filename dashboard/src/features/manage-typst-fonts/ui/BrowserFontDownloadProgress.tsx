import { useEffect, useRef } from "react";
import { formatBytes } from "@/shared/lib/formatters";
import type { useBrowserFontDownload } from "@/features/manage-typst-fonts/model/useBrowserFontDownload";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { CopyButton } from "@/shared/ui/copy-button";
import { Progress } from "@/shared/ui/progress";

export function BrowserFontDownloadProgress({
  download,
}: {
  download: ReturnType<typeof useBrowserFontDownload>;
}) {
  const { transfer, running, elapsed } = download;
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (transfer?.phase === "connecting") panel.current?.scrollIntoView({ block: "nearest" });
  }, [transfer?.phase]);
  if (!transfer) return null;
  return (
    <div ref={panel} className="grid min-w-0 gap-3">
      <h3 className="m-0 text-base font-medium">浏览器下载：{transfer.font.name}</h3>
      {running && (
        <p className="m-0 text-sm">
          {transfer.phase === "connecting" ? "正在连接字体来源" : "正在接收字体"}；已接收{" "}
          {formatBytes(transfer.received)}
          {transfer.total
            ? ` / ${formatBytes(transfer.total)}`
            : "（来源尚未提供总大小）"}；已用{" "}
          {elapsed} 秒
        </p>
      )}
      {transfer.total !== null && (
        <Progress
          label="浏览器字体下载进度"
          value={transfer.total > 0 ? (transfer.received / transfer.total) * 100 : null}
          variant={
            transfer.phase === "failed"
              ? "destructive"
              : transfer.phase === "saved"
                ? "success"
                : "info"
          }
        />
      )}
      <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
        <span className="min-w-0 break-all font-mono">下载地址：{transfer.font.download_url}</span>
        <CopyButton text={transfer.font.download_url} label="复制字体下载地址">
          复制地址
        </CopyButton>
      </div>
      {running && (
        <div>
          <Button variant="outline" onClick={download.cancel}>
            取消浏览器下载
          </Button>
        </div>
      )}
      {transfer.phase === "failed" && <Alert variant="destructive">{transfer.error}</Alert>}
      {transfer.phase === "cancelled" && (
        <Alert>浏览器下载已取消，未提交保存，也未安装到插件。</Alert>
      )}
      {transfer.phase === "saved" && (
        <Alert variant="success">
          字体已交给浏览器保存，请在浏览器下载列表确认
          <AlertDescription>
            下载到电脑后，点击对应行「上传此字体」或「替换」，才会安装到插件服务器。
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
