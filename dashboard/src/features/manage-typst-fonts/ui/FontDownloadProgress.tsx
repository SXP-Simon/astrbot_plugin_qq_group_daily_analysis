import { Alert, Button, List, Progress, Space, Typography } from "antd";
import type { useFontDownload } from "../model/useFontDownload";
import { formatBytes } from "../../../shared/lib/formatters";

export function FontDownloadProgress({ download }: { download: ReturnType<typeof useFontDownload> }) {
  const { progress, running, error, cancelled, cancelling, cancel, transfer, progressError, fallbacks } = download;
  return <Space direction="vertical" style={{ width: "100%" }}>
    {error && <Alert type="error" showIcon message={error} />}
    {fallbacks.length > 0 && <Alert type="info" showIcon message={`CDN 未完成，已自动改用 GitHub Raw 重试：${fallbacks.join("、")}`} />}
    {progress.total > 0 && <>
      <Progress percent={Math.round(progress.done / progress.total * 100)} status={cancelled ? "normal" : running ? "active" : progress.failed.length ? "exception" : "success"} />
      <Typography.Text>字体处理 {progress.done}/{progress.total}，成功 {progress.done - progress.failed.length}，失败 {progress.failed.length}{progress.current ? `；正在下载 ${progress.current}` : ""}</Typography.Text>
      {running && transfer && <>
        <Typography.Text>{({ connecting: "正在连接来源", downloading: "正在接收字体", validating: "正在校验并保存字体" })[transfer.phase]}：{formatBytes(transfer.received)}{transfer.total ? ` / ${formatBytes(transfer.total)}` : "（来源未提供总大小）"}；已用 {Math.round(transfer.elapsed_seconds)} 秒</Typography.Text>
        {transfer.total && <Progress size="small" percent={Math.min(100, Math.round(transfer.received / transfer.total * 100))} status="active" />}
        <Typography.Text type="secondary" style={{ overflowWrap: "anywhere" }}>实际来源：{transfer.url}</Typography.Text>
        {transfer.idle_seconds >= 5 && <Alert showIcon type="warning" message={`已 ${Math.floor(transfer.idle_seconds)} 秒未收到新数据；连接最多等待 10 秒，传输连续无数据 20 秒后终止。请检查插件服务器到上述来源的网络或代理。`} />}
      </>}
      {running && progressError && <Alert type="warning" showIcon message={progressError} />}
      {running && <Button loading={cancelling} onClick={() => void cancel()}>取消下载</Button>}
      {!running && cancelled && <Alert showIcon type="info" message="下载已取消，已完成的字体会保留；再次下载仅补齐缺失文件。" />}
      {!running && !cancelled && <Alert showIcon type={progress.failed.length ? "warning" : "success"} message={progress.failed.length ? "部分字体未完成，请查看下方具体原因；可切换来源、检查服务器代理或上传同名字体，已完成文件会保留" : "字体下载完成"} />}
      {progress.failed.length > 0 && <List size="small" style={{ maxHeight: 200, overflowY: "auto" }} dataSource={progress.failed} renderItem={file => <List.Item><Typography.Text type="danger">{file.name}：{file.message}</Typography.Text></List.Item>} />}
    </>}
  </Space>;
}
