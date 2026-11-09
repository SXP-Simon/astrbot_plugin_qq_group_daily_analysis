import type { useFontDownload } from "@/features/manage-typst-fonts/model/useFontDownload";
import { formatBytes } from "@/shared/lib/formatters";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Progress } from "@/shared/ui/progress";

export function FontDownloadProgress({
  download,
}: {
  download: ReturnType<typeof useFontDownload>;
}) {
  const {
    progress,
    running,
    error,
    cancelled,
    cancelling,
    cancel,
    transfer,
    progressError,
    fallbacks,
  } = download;
  return (
    <div className="grid min-w-0 gap-3">
      {error && <Alert variant="destructive">{error}</Alert>}
      {fallbacks.length > 0 && (
        <Alert>CDN 未完成，已自动改用 GitHub Raw 重试：{fallbacks.join("、")}</Alert>
      )}
      {progress.total > 0 && (
        <>
          <Progress
            label="字体文件处理进度"
            value={(progress.done / progress.total) * 100}
            variant={
              cancelled
                ? "info"
                : progress.failed.length
                  ? "warning"
                  : running
                    ? "default"
                    : "success"
            }
          />
          <p className="m-0 break-words text-sm">
            字体处理 {progress.done}/{progress.total}，成功 {progress.done - progress.failed.length}
            ，失败 {progress.failed.length}
            {progress.current ? `；正在下载 ${progress.current}` : ""}
          </p>
          {running && transfer && (
            <>
              <p className="m-0 text-sm">
                {
                  {
                    connecting: "正在连接来源",
                    downloading: "正在接收字体",
                    validating: "正在校验并保存字体",
                  }[transfer.phase]
                }
                ：{formatBytes(transfer.received)}
                {transfer.total ? ` / ${formatBytes(transfer.total)}` : "（来源未提供总大小）"}
                ；已用 {Math.round(transfer.elapsed_seconds)} 秒
              </p>
              {transfer.total !== null && transfer.total > 0 && (
                <Progress
                  label="当前字体下载进度"
                  value={(transfer.received / transfer.total) * 100}
                  variant="info"
                />
              )}
              <p className="m-0 break-all font-mono text-xs text-muted-foreground">
                实际来源：{transfer.url}
              </p>
              {transfer.idle_seconds >= 5 && (
                <Alert variant="warning">
                  已 {Math.floor(transfer.idle_seconds)} 秒未收到新数据；连接最多等待 10
                  秒，传输连续无数据 20 秒后终止。请检查插件服务器到上述来源的网络或代理。
                </Alert>
              )}
            </>
          )}
          {running && progressError && <Alert variant="warning">{progressError}</Alert>}
          {running && (
            <div>
              <Button variant="outline" disabled={cancelling} onClick={() => void cancel()}>
                {cancelling ? "正在取消…" : "取消下载"}
              </Button>
            </div>
          )}
          {!running && cancelled && (
            <Alert>下载已取消，已完成的字体会保留；再次下载仅补齐缺失文件。</Alert>
          )}
          {!running && !cancelled && (
            <Alert variant={progress.failed.length ? "warning" : "success"}>
              {progress.failed.length
                ? "部分字体未完成，请查看下方具体原因；可切换来源、检查服务器代理或上传同名字体，已完成文件会保留"
                : "字体下载完成"}
            </Alert>
          )}
          {progress.failed.length > 0 && (
            <ul
              aria-label="未完成的字体"
              className="m-0 max-h-52 list-none overflow-auto p-0 text-sm text-destructive"
            >
              {progress.failed.map((file) => (
                <li
                  key={file.name}
                  className="break-words border-b border-border py-2 last:border-0"
                >
                  {file.name}：{file.message}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
