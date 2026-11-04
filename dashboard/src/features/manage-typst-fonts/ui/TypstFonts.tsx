import { FontDownloadProgress } from "./FontDownloadProgress";
import { useState } from "react";
import { Alert, Button, Select, Space, Tag, Typography } from "antd";
import { KNOWN_TEMPLATES } from "../../../entities/report/model/templates";
import { useTypstFonts } from "../model/useTypstFonts";

export function TypstFonts({ cdnBaseUrl }: { cdnBaseUrl: string }) {
  const vm = useTypstFonts(cdnBaseUrl);
  const [theme, setTheme] = useState("HatsuneMiku");
  const group = vm.status?.groups?.find(item => item.theme === theme);
  return <Space direction="vertical" style={{ width: "100%", marginTop: 12 }}>
    <Typography.Text strong>Typst 字体</Typography.Text>
    <Typography.Text type="secondary">
      按内置模板补齐字体，包含简体、繁体、日文、Emoji 和符号等共享基础字库。所有字体保存在本插件 data 目录，跨模板复用。
    </Typography.Text>
    <Select aria-label="字体模板" style={{ width: "100%" }} value={theme} disabled={vm.loading || !vm.status?.groups?.length}
      onChange={setTheme} options={vm.status?.groups?.map(item => ({ value: item.theme,
        label: KNOWN_TEMPLATES.find(template => template.key === item.theme)?.name || item.theme }))} />
    {vm.status && <>
      <Alert type={group?.ready ? "success" : "info"} showIcon
        message={group ? group.ready ? "所选模板字体已就绪" : `所选模板还需下载 ${group.missing.length} / ${group.required.length} 个字体文件`
          : vm.status.ready ? "全部预设字体已就绪" : `全部预设还缺 ${vm.status.missing.length} 个字体文件`} />
      <Typography.Text type="secondary" copyable>{vm.status.directory}</Typography.Text>
      <Space wrap>{group?.required.map(file => <Tag key={file} color={group.missing.includes(file) ? "default" : "success"}>{file}</Tag>)}</Space>
    </>}
    <Space wrap>
      <Button loading={vm.operation === "selected"} disabled={vm.loading || !group || group.ready} onClick={() => void vm.run(true, theme)}>
        下载所选模板字体
      </Button>
      <Button loading={vm.operation === "all"} disabled={vm.loading || !vm.status || vm.status.ready} onClick={() => void vm.run(true)}>下载全部预设字体</Button>
      <Button loading={vm.operation === "refresh"} disabled={vm.loading} onClick={() => void vm.run(false)}>刷新字体状态</Button>
    </Space>
    <Typography.Text type="secondary">常规字体使用本方案 CDN；超出 CDN 体积限制的字体从官方源下载。失败后已下载文件会保留，重试仅补缺失文件。自定义模板可将其额外字体放入上述目录。</Typography.Text>
    <Typography.Text type="secondary">预设字体采用 <Typography.Link href="https://openfontlicense.org/open-font-license-official-text/" target="_blank" rel="noreferrer">SIL OFL 1.1</Typography.Link>，下载保留上游原文件及版权信息；自行上传字体前请确认授权。BlueArchive 已改用 Noto Sans。</Typography.Text>
    <FontDownloadProgress download={vm.downloadQueue} />
    {vm.error && <Alert type="error" showIcon message={vm.error} />}
  </Space>;
}
