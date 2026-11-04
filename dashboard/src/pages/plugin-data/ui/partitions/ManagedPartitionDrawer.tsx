import { Alert, Button, Descriptions, Drawer, Space, Tabs, Typography } from "antd";
import { useState, type ReactNode } from "react";
import { usePartitionManager } from "../../model/usePartitionManager";
import { StoredRecordsTab } from "../StoredRecordsTab";
import { ManagedFileList } from "../../../../features/manage-stored-files/ui/ManagedFileList";
import { FileContentDialog } from "../../../../features/manage-stored-files/ui/FileContentDialog";
import { FileEditorDialog } from "../../../../features/manage-stored-files/ui/FileEditorDialog";
import { FontManager } from "../../../../features/manage-typst-fonts/ui/FontManager";
import { TemplatePackages } from "../../../../features/install-template/ui/TemplatePackages";
import { TemplateInstallModal } from "../../../../features/install-template/ui/TemplateInstallModal";
import { TemplateResources } from "../../../../features/manage-template-resources/ui/TemplateResources";
import { ConfigBackupsViewer } from "../../../../features/view-config-backups/ui/ConfigBackupsViewer";
import { DEFAULT_TEMPLATE_CDN_BASE_URL } from "../../../../entities/config/model/renderingConfig";

export function ManagedPartitionDrawer({ manager }: { manager: ReturnType<typeof usePartitionManager> }) {
  const [resourceVersion, setResourceVersion] = useState(0);
  const { files: vm, partition, references, links } = manager;
  const specializedManagers: Record<string, ReactNode> = {
    typst_fonts: <FontManager key={manager.fontSelection?.sequence || 0} initialSelection={manager.fontSelection || undefined} onChanged={manager.refresh} />,
    avatar_storage: <StoredRecordsTab onlyKind="avatar" />,
  };
  return <Drawer open={!!vm.partition} title={vm.partition?.name} width="min(1100px, 96vw)" onClose={() => vm.select(null)} destroyOnClose>
    {partition && <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Descriptions size="small" column={1} items={[{ key: "path", label: "存储目录", children: <Typography.Text copyable>{partition.directory}</Typography.Text> }, { key: "use", label: "用途", children: partition.description }]} />
      <Alert showIcon type={partition.deletable ? "warning" : "info"} message={partition.impact} />
      {vm.listError && <Alert type="error" showIcon message={vm.listError} action={<Button onClick={() => void vm.load()}>重试列表</Button>} />}
      {partition.key === "config_files" && <><Typography.Text type="secondary">新增图片需在配置中心选择对应字段；这里可预览、同名替换、复制引用路径与清理文件。下列引用来自当前已保存的插件配置。</Typography.Text>{references.error && <Alert type="warning" showIcon message={references.error} description="无法确认引用关系，请先刷新或打开配置中心检查。" action={<Button onClick={() => void references.refresh()}>重新检查</Button>} />}</>}
      {(links.length > 0 || partition.key === "config_backups") && <Space wrap>{links.map(link => <Button key={`${link.kind}:${link.destination}`} onClick={() => manager.navigate(link)}>{link.label}</Button>)}{partition.key === "config_backups" && <ConfigBackupsViewer />}</Space>}
      {partition.key === "typst_fonts" && manager.fontSelection && <Button onClick={() => manager.navigate({ kind: "page", destination: "config", label: "返回 Typst 方案" })}>返回 Typst 方案</Button>}
      {partition.key === "custom_templates" && <TemplatePackages groups={vm.groups} directory={vm.directory} loading={vm.loading} busy={vm.busy} onSelect={vm.selectDirectory} onInstall={() => manager.setInstalling(true)} onCreate={() => vm.setEditor({ name: "", text: "" })} onRefresh={manager.refresh} />}
      {specializedManagers[partition.key] || (partition.key === "custom_templates" && !vm.directory ? null : <Tabs key={`${partition.key}:${vm.directory}`} defaultActiveKey={partition.key === "template_resources" ? "download" : "files"} onChange={key => { manager.refresh(); if (key === "download") setResourceVersion(value => value + 1); }} items={[
        ...(partition.key === "template_resources" ? [{ key: "download", label: "主题素材状态", children: <TemplateResources refreshVersion={resourceVersion} cdnBaseUrl={DEFAULT_TEMPLATE_CDN_BASE_URL} onChanged={manager.refresh} /> }] : []),
        { key: "files", label: partition.key === "template_resources" ? "本地素材与替换" : partition.key === "state" ? "数据库与状态占用" : partition.key === "typst_jobs" ? "只读诊断文件" : "文件列表", children: <ManagedFileList vm={vm} partition={partition} references={references} /> },
      ]} />)}
    </Space>}
    {partition?.key !== "typst_fonts" && <FileContentDialog vm={vm} editor={vm.editor} setEditor={vm.setEditor} references={partition?.key === "config_files" && vm.content ? references.references.get(vm.content.name) : undefined} />}
    {!vm.content && <FileEditorDialog vm={vm} editor={vm.editor} setEditor={vm.setEditor} />}
    <TemplateInstallModal open={manager.installing} onClose={() => manager.setInstalling(false)} onInstalled={result => { vm.selectDirectory(result.name); void vm.refresh(); }} />
  </Drawer>;
}
