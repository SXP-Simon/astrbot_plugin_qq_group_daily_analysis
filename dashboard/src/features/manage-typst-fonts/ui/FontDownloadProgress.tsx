import { Alert, List, Progress, Space, Typography } from "antd";
import type { useFontDownload } from "../model/useFontDownload";

export function FontDownloadProgress({ download }: { download: ReturnType<typeof useFontDownload> }) {
  const { progress, running, error } = download;
  return <Space direction="vertical" style={{ width: "100%" }}>
    {error && <Alert type="error" showIcon message={error} />}
    {progress.total > 0 && <>
      <Progress percent={Math.round(progress.done / progress.total * 100)} status={running ? "active" : progress.failed.length ? "exception" : "success"} />
      <Typography.Text>字体处理 {progress.done}/{progress.total}，成功 {progress.done - progress.failed.length}，失败 {progress.failed.length}{progress.current ? `；正在下载 ${progress.current}` : ""}</Typography.Text>
      {!running && <Alert showIcon type={progress.failed.length ? "warning" : "success"} message={progress.failed.length ? "部分字体未完成，可更换 CDN 后重试；已完成文件会保留" : "字体下载完成"} />}
      {progress.failed.length > 0 && <List size="small" style={{ maxHeight: 200, overflowY: "auto" }} dataSource={progress.failed} renderItem={file => <List.Item><Typography.Text type="danger">{file.name}：{file.message}</Typography.Text></List.Item>} />}
    </>}
  </Space>;
}
