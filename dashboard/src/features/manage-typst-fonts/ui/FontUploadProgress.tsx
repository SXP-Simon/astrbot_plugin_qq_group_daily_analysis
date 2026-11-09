import type { useFontUpload } from "@/features/manage-typst-fonts/model/useFontUpload";
import { formatBytes } from "@/shared/lib/formatters";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Progress } from "@/shared/ui/progress";

export function FontUploadProgress({ upload }: { upload: ReturnType<typeof useFontUpload> }) {
  const { progress, elapsed, running, cancelling, cancel } = upload;
  if (!progress) return null;
  return (
    <div className="grid min-w-0 gap-3">
      <p className="m-0 break-words text-sm">
        上传 {progress.name}：服务器已接收 {formatBytes(progress.received)} /{" "}
        {formatBytes(progress.total)}，已用 {elapsed} 秒
      </p>
      <Progress
        label="字体上传进度"
        value={progress.total > 0 ? (progress.received / progress.total) * 100 : null}
        variant={
          progress.phase === "failed"
            ? "destructive"
            : progress.phase === "saved"
              ? "success"
              : "info"
        }
      />
      {running && (
        <>
          <p className="m-0 text-sm text-muted-foreground">
            文件接收完成后会校验并保存，然后刷新列表。
          </p>
          <div>
            <Button variant="outline" disabled={cancelling} onClick={() => void cancel()}>
              {cancelling ? "正在取消…" : "取消上传"}
            </Button>
          </div>
        </>
      )}
      {progress.phase === "saved" && (
        <Alert variant="success">字体已上传并保存，列表正在刷新。</Alert>
      )}
      {progress.phase === "cancelled" && (
        <Alert>上传已取消，暂存分块已清理；已保存的字体会保留。</Alert>
      )}
      {progress.error && progress.phase !== "cancelled" && (
        <Alert variant="destructive">{progress.error}</Alert>
      )}
    </div>
  );
}
