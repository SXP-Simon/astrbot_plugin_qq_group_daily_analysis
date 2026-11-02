import { Alert, Button, Space, Tag, Typography } from "antd";
import { useTypstFonts } from "../model/useTypstFonts";

export function TypstFonts({ cdnBaseUrl }: { cdnBaseUrl: string }) {
  const vm = useTypstFonts(cdnBaseUrl);
  return <Space direction="vertical" style={{ width: "100%", marginTop: 12 }}>
    <Typography.Text strong>Typst 字体</Typography.Text>
    <Typography.Text type="secondary">
      预设含简体、繁体、日文字体及 Miku 数字字体，下载到本插件数据目录，可跨报告复用。
    </Typography.Text>
    {vm.status && <>
      <Alert type={vm.status.ready ? "success" : "info"} showIcon
        message={vm.status.ready ? "预设字体已就绪" : `还需下载 ${vm.status.missing.length} 个字体文件`} />
      <Typography.Text type="secondary" copyable>{vm.status.directory}</Typography.Text>
      <Space wrap>{vm.status.files.map((file) => <Tag key={file}>{file}</Tag>)}</Space>
    </>}
    <Space>
      <Button loading={vm.loading} disabled={vm.status?.ready} onClick={() => void vm.run(true)}>
        {vm.loading ? "正在处理字体…" : "下载预设字体"}
      </Button>
      <Button disabled={vm.loading} onClick={() => void vm.run(false)}>刷新字体状态</Button>
    </Space>
    <Typography.Text type="secondary">使用本方案的资源 CDN 下载；已下载的文件会保留，失败后可更换 CDN 重试。</Typography.Text>
    {vm.error && <Alert type="error" showIcon message={vm.error} />}
  </Space>;
}
