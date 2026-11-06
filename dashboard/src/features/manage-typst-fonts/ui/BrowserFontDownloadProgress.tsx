import { Alert, Button, Progress, Space, Typography } from "antd";
import { useEffect, useRef } from "react";
import { formatBytes } from "../../../shared/lib/formatters";
import type { useBrowserFontDownload } from "../model/useBrowserFontDownload";

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
    <div ref={panel}>
      <Space direction="vertical" style={{ width: "100%" }}>
        <Typography.Text strong>浏览器下载：{transfer.font.name}</Typography.Text>
        {running && (
          <Typography.Text>
            {transfer.phase === "connecting" ? "正在连接字体来源" : "正在接收字体"}；已接收{" "}
            {formatBytes(transfer.received)}
            {transfer.total
              ? ` / ${formatBytes(transfer.total)}`
              : "（来源尚未提供总大小）"}；已用{" "}
            {elapsed} 秒
          </Typography.Text>
        )}
        {transfer.total !== null && (
          <Progress
            percent={Math.min(100, Math.floor((transfer.received / transfer.total) * 100))}
            status={
              transfer.phase === "failed"
                ? "exception"
                : running
                  ? "active"
                  : transfer.phase === "saved"
                    ? "success"
                    : "normal"
            }
          />
        )}
        <Typography.Paragraph
          copyable={{ text: transfer.font.download_url }}
          style={{ marginBottom: 0, overflowWrap: "anywhere", userSelect: "text" }}
        >
          下载地址：{transfer.font.download_url}
        </Typography.Paragraph>
        {running && <Button onClick={download.cancel}>取消浏览器下载</Button>}
        {transfer.phase === "failed" && <Alert type="error" showIcon message={transfer.error} />}
        {transfer.phase === "cancelled" && (
          <Alert type="info" showIcon message="浏览器下载已取消，未提交保存，也未安装到插件。" />
        )}
        {transfer.phase === "saved" && (
          <Alert
            type="success"
            showIcon
            message="字体已交给浏览器保存，请在浏览器下载列表确认"
            description="下载到电脑后，点击对应行「上传此字体」或「替换」，才会安装到插件服务器。"
          />
        )}
      </Space>
    </div>
  );
}
