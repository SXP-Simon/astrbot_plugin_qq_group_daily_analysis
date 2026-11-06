import { Alert, Button, Progress, Space, Typography } from "antd";
import type { useFontUpload } from "../model/useFontUpload";
import { formatBytes } from "../../../shared/lib/formatters";

export function FontUploadProgress({ upload }: { upload: ReturnType<typeof useFontUpload> }) {
  const { progress, elapsed, running, cancelling, cancel } = upload;
  if (!progress) return null;
  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Typography.Text>
        上传 {progress.name}：服务器已接收 {formatBytes(progress.received)} /{" "}
        {formatBytes(progress.total)}，已用 {elapsed} 秒
      </Typography.Text>
      <Progress
        percent={Math.floor((progress.received / progress.total) * 100)}
        status={progress.phase === "failed" ? "exception" : running ? "active" : "normal"}
      />
      {running && (
        <>
          <Typography.Text type="secondary">
            使用二进制分块上传；最后一块完成后校验并保存。上传完成后单独刷新列表。
          </Typography.Text>
          <Button onClick={() => void cancel()} loading={cancelling}>
            取消上传
          </Button>
        </>
      )}
      {progress.phase === "saved" && (
        <Alert showIcon type="success" message="字体已上传并保存，列表正在刷新。" />
      )}
      {progress.phase === "cancelled" && (
        <Alert showIcon type="info" message="上传已取消，暂存分块已清理；已保存的字体会保留。" />
      )}
      {progress.error && progress.phase !== "cancelled" && (
        <Alert showIcon type="error" message={progress.error} />
      )}
    </Space>
  );
}
