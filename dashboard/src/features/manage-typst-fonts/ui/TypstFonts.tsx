import { Alert, Button, Space, Tag, Typography } from "antd";
import { useTypstFonts } from "../model/useTypstFonts";

export function TypstFonts({ cdnBaseUrl }: { cdnBaseUrl: string }) {
  const vm = useTypstFonts(cdnBaseUrl);
  return <Space direction="vertical" style={{ width: "100%", marginTop: 12 }}>
    <Typography.Text strong>Typst 字体</Typography.Text>
    <Typography.Text type="secondary">
      预设包含简体、繁体、日文及内置主题使用的字体，下载到本插件数据目录，可跨报告复用。
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
    <Typography.Text type="secondary">常规字体使用本方案 CDN；超出 CDN 体积限制的字体从官方源下载。已下载的文件会保留，失败后可重试。</Typography.Text>
    {vm.error && <Alert type="error" showIcon message={vm.error} />}
  </Space>;
}
