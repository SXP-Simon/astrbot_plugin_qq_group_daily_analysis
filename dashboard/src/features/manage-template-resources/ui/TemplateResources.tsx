import { useEffect, useState } from "react";
import { Alert, AutoComplete, Button, List, Progress, Space, Tag, Typography } from "antd";
import { TEMPLATE_CDN_PRESETS } from "../../../entities/config/model/renderingConfig";
import { KNOWN_TEMPLATES } from "../../../entities/report/model/templates";
import { useTemplateResources } from "../model/useTemplateResources";

export function TemplateResources({ cdnBaseUrl }: { cdnBaseUrl: string }) {
  const [cdn, setCdn] = useState(cdnBaseUrl);
  useEffect(() => setCdn(cdnBaseUrl), [cdnBaseUrl]);
  const vm = useTemplateResources(cdn);
  const missing = vm.status?.groups.flatMap((group) => group.files).filter((file) => !file.available).length ?? 0;
  return <Space direction="vertical" style={{ width: "100%", marginTop: 16 }}>
    <Typography.Text strong>Typst 模板素材</Typography.Text>
    <Typography.Text type="secondary">按主题下载图标和角色原图到插件 data 目录，已有文件会复用。缺图时渲染器会从方案 CDN 获取。Emoji 直接使用字体。</Typography.Text>
    <AutoComplete aria-label="素材下载 CDN" style={{ width: "100%" }} value={cdn} options={TEMPLATE_CDN_PRESETS}
      disabled={vm.running} onChange={setCdn} placeholder="选择国内、海外 CDN，或输入自定义根地址" />
    <Typography.Text type="secondary">这里的 CDN 用于本次下载；自动补图使用渲染方案中的 CDN。</Typography.Text>
    <Space>
      <Button loading={vm.running} disabled={vm.loading || !missing} onClick={() => void vm.download()}>下载全部缺失素材</Button>
      <Button loading={vm.loading} disabled={vm.running} onClick={() => void vm.refresh()}>刷新素材状态</Button>
    </Space>
    {vm.progress.total > 0 && <>
      <Progress percent={Math.round(vm.progress.done / vm.progress.total * 100)} status={vm.progress.failed.length ? "exception" : vm.running ? "active" : "success"} />
      <Typography.Text>完成 {vm.progress.done}/{vm.progress.total}，成功 {vm.progress.done - vm.progress.failed.length}，失败 {vm.progress.failed.length}</Typography.Text>
      {!vm.running && <Alert showIcon type={vm.progress.failed.length ? "warning" : "success"}
        message={vm.progress.failed.length ? "部分素材未下载成功，可更换 CDN 后重试；已有文件会跳过" : "本轮素材下载完成"} />}
    </>}
    {vm.error && <Alert type="error" showIcon message={vm.error} />}
    {vm.progress.failed.length > 0 && <List size="small" style={{ maxHeight: 200, overflowY: "auto" }} dataSource={vm.progress.failed}
      renderItem={(file) => <List.Item><Typography.Text type="danger" style={{ overflowWrap: "anywhere" }}>{file.name}：{file.message}</Typography.Text></List.Item>} />}
    {vm.status && <>
      <Typography.Text type="secondary" copyable>{vm.status.directory}</Typography.Text>
      <List size="small" dataSource={vm.status.groups} renderItem={(group) => {
        const count = group.files.filter((file) => file.available).length;
        return <List.Item actions={[<Button key="download" size="small" disabled={vm.running || vm.loading || count === group.files.length}
          onClick={() => void vm.download(group.theme)}>下载 {group.theme} 素材</Button>]}>
          <Space wrap><Typography.Text>{KNOWN_TEMPLATES.find((item) => item.key === group.theme)?.name || group.theme}</Typography.Text>
            <Tag color={count === group.files.length ? "success" : "default"}>{group.files.length ? `${count}/${group.files.length} 已就绪` : "无需外置素材"}</Tag></Space>
        </List.Item>;
      }} />
    </>}

  </Space>;
}
