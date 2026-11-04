import { FontDownloadProgress } from "./FontDownloadProgress";
import { useContext, useState } from "react";
import { Alert, Button, Select, Space, Tag, Typography } from "antd";
import { KNOWN_TEMPLATES } from "../../../entities/report/model/templates";
import { useTypstFonts } from "../model/useTypstFonts";
import { FONT_DOWNLOAD_SOURCES } from "../../../entities/config/model/typstFonts";
import { FontManagementContext } from "../model/FontManagementContext";
import { ExternalLink } from "../../../shared/ui/ExternalLink";

export function TypstFonts({ cdnBaseUrl }: { cdnBaseUrl: string }) {
  const navigation = useContext(FontManagementContext);
  const vm = useTypstFonts(cdnBaseUrl, navigation?.version);
  const [theme, setTheme] = useState("HatsuneMiku");
  const group = vm.status?.groups?.find(item => item.theme === theme);
  return <Space direction="vertical" style={{ width: "100%", marginTop: 12 }}>
    <Typography.Text strong>Typst 字体</Typography.Text>
    <Typography.Text type="secondary">
      按模板补齐缺失字体，包含简体、繁体、日文、Emoji 和符号等共享基础字库。下载前会重新核对缺失项，CDN 失败自动尝试 Raw 备用源。所有字体保存在本插件 data 目录，跨模板复用。
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
      <Select aria-label="字体下载来源" value={vm.downloadQueue.source} disabled={vm.loading} options={FONT_DOWNLOAD_SOURCES} onChange={vm.downloadQueue.setSource} style={{ width: 300, maxWidth: "100%" }} />
      <Button loading={vm.operation === "selected"} disabled={vm.loading || !group || group.ready} onClick={() => void vm.run(true, theme)}>
        下载所选模板字体
      </Button>
      <Button loading={vm.operation === "all"} disabled={vm.loading || !vm.status || vm.status.ready} onClick={() => void vm.run(true)}>下载全部预设字体</Button>
      <Button loading={vm.operation === "refresh"} disabled={vm.loading} onClick={() => void vm.run(false)}>刷新字体状态</Button>
      {navigation && <Button disabled={vm.loading} onClick={() => navigation.open({ theme, cdnBaseUrl, source: vm.downloadQueue.source })}>管理 / 上传字体</Button>}
    </Space>
    <Typography.Text type="secondary">CDN 优先模式下，大字库（含 ATRI 文楷）仍从固定 GitHub Raw 来源直连；也可选择全部字体走 Raw，绕过镜像 CDN 的体积限制。下载由插件服务器执行，Raw 无法访问时需检查服务器网络或代理；更换 CDN 不会改变直连地址。失败重试仅补缺失文件，也可在字体管理中上传同名文件。</Typography.Text>
    <Typography.Text type="secondary">下载失败时可打开「管理 / 上传字体」，进入「数据管理 → 存储分区明细与管理 → Typst 字体」，查看对应版本的上游与下载链接。浏览器下载成功后，使用对应字体行的上传按钮即可自动按预设命名。</Typography.Text>
    <Typography.Text type="secondary">预设字体采用 <ExternalLink href="https://openfontlicense.org/open-font-license-official-text/">SIL OFL 1.1</ExternalLink>，下载保留上游原文件及版权信息；自行上传字体前请确认授权。BlueArchive 已改用 Noto Sans。</Typography.Text>
    {(vm.downloadQueue.error || vm.downloadQueue.progress.total > 0) && <FontDownloadProgress download={vm.downloadQueue} />}
    {vm.error && <Alert type="error" showIcon message={vm.error} />}
  </Space>;
}
