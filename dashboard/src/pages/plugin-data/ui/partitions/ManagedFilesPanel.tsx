import { StoredRecordsTab } from "../StoredRecordsTab";
import { useState } from "react";
import { Alert, Button, Card, Col, Descriptions, Drawer, Input, Popconfirm, Progress, Row, Space, Statistic, Table, Tabs, Tag, Typography, Upload, message } from "antd";
import { FileOutlined, FolderOpenOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons";
import { FileContentDialog } from "./FileContentDialog";
import { FileEditorDialog, type FileDraft } from "./FileEditorDialog";
import { useManagedFiles } from "../../model/useManagedFiles";
import { useConfigFileReferences } from "../../model/useConfigFileReferences";
import { partitionPresentation } from "../../model/partitionPresentation";
import { formatBytes } from "../../../../shared/lib/formatters";
import { FontManager } from "./FontManager";
import { TemplatePackages } from "./TemplatePackages";
import { TemplateResources } from "../../../../features/manage-template-resources/ui/TemplateResources";
import { ConfigBackupsViewer } from "../../../../features/view-config-backups/ui/ConfigBackupsViewer";
import { TemplateInstallModal } from "../../../../features/install-template/ui/TemplateInstallModal";
import { DEFAULT_TEMPLATE_CDN_BASE_URL } from "../../../../entities/config/model/renderingConfig";
import type { ManagedFile, ManagedPartition } from "../../../../entities/plugin-data/api/managedFilesApi";

export function ManagedFilesPanel({ onNavigate, onOpenDataTab }: { onNavigate?: (page: "reports" | "config" | "traces") => void; onOpenDataTab?: (tab: "records" | "incremental" | "checkpoints") => void }) {
  const vm = useManagedFiles();
  const [editor, setEditor] = useState<FileDraft | null>(null);
  const [installing, setInstalling] = useState(false);
  const totalBytes = vm.partitions.reduce((sum, item) => sum + item.size_bytes, 0);
  const totalFiles = vm.partitions.reduce((sum, item) => sum + item.count, 0);

  const activePartition = vm.partitions.find(item => item.key === vm.partition?.key) || vm.partition;
  const references = useConfigFileReferences(activePartition?.key === "config_files");
  const templatePrefix = activePartition?.key === "custom_templates" && vm.directory && vm.directory !== "." ? `${vm.directory}/` : "";
  const fileAction = ["typst_assets", "preview_cache"].includes(activePartition?.key || "") ? "清理" : "删除";

  return <Space direction="vertical" size="middle" style={{ width: "100%" }}>
    <Row gutter={[12, 12]}>
      <Col xs={24} sm={8}><Card size="small"><Statistic title="插件文件占用" value={formatBytes(totalBytes)} /><Typography.Text type="secondary">共 {totalFiles} 个文件</Typography.Text></Card></Col>
      <Col xs={24} sm={8}><Card size="small"><Statistic title="受管理分区" value={vm.partitions.length} /><Typography.Text type="secondary">按模块提供对应操作</Typography.Text></Card></Col>
      <Col xs={24} sm={8}><Card size="small"><Statistic title="字体与原始素材" value={formatBytes(vm.partitions.filter(item => ["typst_fonts", "template_resources"].includes(item.key)).reduce((sum, item) => sum + item.size_bytes, 0))} /><Typography.Text type="secondary">支持按主题补齐与单项维护</Typography.Text></Card></Col>
    </Row>
    {vm.error && <Alert type="error" showIcon message={vm.error} action={<Button onClick={() => void vm.refresh()}>重试</Button>} />}
    <Card size="small" title={<Space><FolderOpenOutlined />存储分区明细与管理</Space>} extra={<Button icon={<ReloadOutlined />} onClick={() => void vm.refresh()}>刷新概览</Button>}>
      <Table<ManagedPartition> rowKey="key" size="small" dataSource={vm.partitions} pagination={false} scroll={{ x: 860 }} columns={[
        { title: "数据分区", width: 220, render: (_, item) => <Space direction="vertical" size={0}><Typography.Text strong>{item.name}</Typography.Text><Typography.Text type="secondary" style={{ fontSize: 11, maxWidth: 210 }} ellipsis={{ tooltip: item.directory }}>{item.directory}</Typography.Text></Space> },
        { title: "文件", dataIndex: "count", align: "right", width: 65 },
        { title: "占用空间", width: 100, align: "right", render: (_, item) => formatBytes(item.size_bytes) },
        { title: "占比", width: 115, render: (_, item) => <Progress size="small" percent={totalBytes ? Math.round(item.size_bytes / totalBytes * 100) : 0} /> },
        { title: "分区用途与能力", render: (_, item) => <Space direction="vertical" size={2}><Typography.Text>{item.description}</Typography.Text><Space size={[0, 4]} wrap>{partitionPresentation[item.key]?.capabilities.map(label => <Tag key={label} color="blue">{label}</Tag>)}</Space></Space> },
        { title: "操作", fixed: "right", width: 85, render: (_, item) => <Button type="link" onClick={() => { setEditor(null); setInstalling(false); vm.select(item); }}>管理</Button> },
      ]} />
    </Card>
    <Drawer open={!!vm.partition} title={vm.partition?.name} width="min(1100px, 96vw)" onClose={() => vm.select(null)} destroyOnClose>
      {activePartition && <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        <Descriptions size="small" column={1} items={[{ key: "path", label: "存储目录", children: <Typography.Text copyable>{activePartition.directory}</Typography.Text> }, { key: "use", label: "用途", children: activePartition.description }]} />
        <Alert showIcon type={activePartition.deletable ? "warning" : "info"} message={activePartition.impact} />
        {vm.listError && <Alert type="error" showIcon message={vm.listError} action={<Button onClick={() => void vm.load()}>重试列表</Button>} />}
        {activePartition.key === "config_files" && <><Typography.Text type="secondary">新增图片需在配置中心选择对应字段；这里可预览、同名替换、复制引用路径与清理文件。下列引用来自当前已保存的插件配置。</Typography.Text>{references.error && <Alert type="warning" showIcon message={references.error} description="无法确认引用关系，请先刷新或打开配置中心检查。" action={<Button onClick={() => void references.refresh()}>重新检查</Button>} />}</>}
        <Space wrap>
          {onNavigate && ["reports", "hosted_reports", "config_files", "config_backups", "state", "typst_jobs"].includes(activePartition.key) && <Button onClick={() => { const page = ["state", "typst_jobs"].includes(activePartition.key) ? "traces" : ["config_files", "config_backups"].includes(activePartition.key) ? "config" : "reports"; vm.select(null); onNavigate(page); }}>{["state", "typst_jobs"].includes(activePartition.key) ? "查看分析执行任务" : activePartition.key === "config_files" ? "在配置中心新增图片与维护引用" : activePartition.key === "config_backups" ? "打开配置中心" : "打开历史报告预览与重绘"}</Button>}
          {onOpenDataTab && ["state", "legacy_history"].includes(activePartition.key) && <Button onClick={() => { vm.select(null); onOpenDataTab("records"); }}>管理当前分析存档</Button>}
          {onOpenDataTab && activePartition.key === "state" && <><Button onClick={() => { vm.select(null); onOpenDataTab("incremental"); }}>管理增量批次</Button><Button onClick={() => { vm.select(null); onOpenDataTab("checkpoints"); }}>管理阶段快照</Button></>}
          {activePartition.key === "config_backups" && <ConfigBackupsViewer />}
        </Space>
        {activePartition.key === "custom_templates" && !vm.directory ? <TemplatePackages groups={vm.groups} loading={vm.loading} onSelect={vm.selectDirectory} onInstall={() => setInstalling(true)} onCreate={() => setEditor({ name: "", text: "" })} onRefresh={() => { void vm.load(); void vm.refresh(); }} /> : activePartition.key === "typst_fonts" ? <FontManager onChanged={() => { void vm.refresh(); }} /> : activePartition.key === "avatar_storage" ? <StoredRecordsTab onlyKind="avatar" /> : <>
        {activePartition.key === "custom_templates" && <Space wrap><Button onClick={() => vm.selectDirectory("")}>返回模板列表</Button><Typography.Text strong>{vm.directory === "." ? "未归组文件" : `模板：${vm.directory}`}</Typography.Text><Typography.Text type="secondary">当前操作仅限此模板内的文件。</Typography.Text></Space>}
        <Tabs key={`${activePartition.key}:${vm.directory}`} defaultActiveKey={activePartition.key === "template_resources" ? "download" : "files"} onChange={() => { void vm.load(); void vm.refresh(); }} items={[
          ...(activePartition.key === "template_resources" ? [{ key: "download", label: "主题素材状态", children: <TemplateResources cdnBaseUrl={DEFAULT_TEMPLATE_CDN_BASE_URL} onChanged={() => { void vm.load(); void vm.refresh(); }} /> }] : []),
          { key: "files", label: activePartition.key === "template_resources" ? "本地素材与替换" : activePartition.key === "state" ? "数据库与状态占用" : activePartition.key === "typst_jobs" ? "只读诊断文件" : "文件列表", children: <Space direction="vertical" style={{ width: "100%" }}>
            <Space wrap>
              <Input.Search aria-label="搜索文件" placeholder="搜索文件名或相对路径" allowClear onSearch={vm.searchFiles} style={{ width: 260 }} />
              <Button icon={<ReloadOutlined />} loading={vm.loading} onClick={() => { vm.clearSelection(); void vm.load(); void vm.refresh(); void references.refresh(); }}>刷新列表</Button>
              {activePartition.writable && activePartition.key !== "config_files" && <Upload showUploadList={false} beforeUpload={async file => {
                if (file.size > 32 * 1024 * 1024) { void message.error("文件不得超过 32 MiB"); return false; }
                const reader = new FileReader();
                reader.onload = () => { setEditor({ name: templatePrefix + file.name, text: "", encoded: String(reader.result).split(",")[1] }); };
                reader.onerror = () => { void message.error("无法读取上传文件"); };
                reader.readAsDataURL(file); return false;
              }}><Button icon={<UploadOutlined />} disabled={vm.busy}>上传文件</Button></Upload>}
              {activePartition.key === "custom_templates" && <Button onClick={() => setEditor({ name: templatePrefix, text: "" })}>新建源码</Button>}
            </Space>
            <Space role="group" aria-label="文件类型筛选" wrap size={[8, 8]}>
              {[{ value: "", label: "全部类型" }, ...(partitionPresentation[activePartition.key]?.filters || [])].map(filter => <Button key={filter.value} size="small" type={vm.extensions === filter.value ? "primary" : "default"} aria-pressed={vm.extensions === filter.value} onClick={() => vm.filterExtensions(filter.value)}>{filter.label}</Button>)}
            </Space>
            {activePartition.deletable && <Space wrap><Typography.Text>已选 {vm.selected.length} 项（最多 200，支持跨页）</Typography.Text>
              <Button size="small" disabled={!vm.selected.length || vm.busy} onClick={vm.clearSelection}>取消选择</Button>
              <Popconfirm title={`${fileAction}已选的 ${vm.selected.length} 个文件？`} description={<Space direction="vertical"><Typography.Text>{activePartition.name}{vm.directory && ` / ${vm.directory}`} · {vm.extensions || "全部类型"} · {vm.search || "无关键词"}</Typography.Text><Typography.Text>{activePartition.impact}</Typography.Text><Typography.Text style={{ maxWidth: 420, overflowWrap: "anywhere" }}>{vm.selected.slice(0, 5).map(file => file.name).join("、")}{vm.selected.length > 5 ? " 等" : ""}</Typography.Text></Space>} okText={`${fileAction}所选`} cancelText="取消" onConfirm={vm.deleteSelected}>
                <Button danger size="small" disabled={!vm.selected.length} loading={vm.busy}>{fileAction}所选</Button>
              </Popconfirm></Space>}
            {vm.deleteResult && <Alert showIcon type={vm.deleteResult.failed.length ? "warning" : "success"} message={`${fileAction}成功 ${vm.deleteResult.deleted.length} 项，失败 ${vm.deleteResult.failed.length} 项`} description={vm.deleteResult.failed.map(file => <div key={file.name}>{file.name}：{file.message}</div>)} />}
            <Table<ManagedFile> rowKey="name" size="small" dataSource={vm.files} loading={vm.loading} locale={{ emptyText: vm.search || vm.extensions ? "没有匹配文件，请调整关键词或文件类型。" : partitionPresentation[activePartition.key]?.empty }} rowSelection={activePartition.deletable ? { selectedRowKeys: vm.selected.map(file => file.name), onChange: vm.selectFiles, preserveSelectedRowKeys: true, getCheckboxProps: file => ({ disabled: vm.busy || vm.selected.length >= 200 && !vm.selected.some(item => item.name === file.name) }) } : undefined} scroll={{ x: 650 }} pagination={{ current: vm.page, total: vm.total, pageSize: 20, showSizeChanger: false, onChange: vm.setPage, showTotal: count => `共 ${count} 个文件` }} columns={[
              { title: "文件名", dataIndex: "name", render: (name: string) => <Typography.Text style={{ overflowWrap: "anywhere" }}><FileOutlined /> {templatePrefix && name.startsWith(templatePrefix) ? name.slice(templatePrefix.length) : name}</Typography.Text> },
              ...(activePartition.key === "config_files" ? [{ title: "配置引用", width: 250, render: (_: unknown, file: ManagedFile) => <Space direction="vertical" size={2}><Typography.Text copyable style={{ fontSize: 12, overflowWrap: "anywhere" }}>{`files/${file.name}`}</Typography.Text><Typography.Text type="secondary" style={{ fontSize: 12, overflowWrap: "anywhere" }}>{references.loading ? "正在检查引用…" : references.error ? "引用关系未确认" : references.references.get(file.name)?.join("、") || "未在已保存配置中找到引用；自定义源码中的引用需自行确认。"}</Typography.Text></Space> }] : []),
              { title: "大小", width: 105, render: (_, file) => formatBytes(file.size_bytes) },
              { title: "修改时间", width: 175, render: (_, file) => new Date(file.modified_at * 1000).toLocaleString() },
              { title: "操作", width: 150, render: (_, file) => file.downloadable ? <Button type="link" disabled={vm.busy} onClick={() => void (file.editable || /^(image\/|text\/|application\/json)/.test(file.media_type) ? vm.inspect(file.name) : vm.download(file.name))}>{file.editable ? "查看 / 编辑" : /^(image\/|text\/html)/.test(file.media_type) ? "预览 / 下载" : /^(text\/|application\/json)/.test(file.media_type) ? "查看内容 / 下载" : "下载文件"}</Button> : <Tag>由模块管理</Tag> },
            ]} />
          </Space> },
        ]} /></>}
      </Space>}
    {activePartition?.key !== "typst_fonts" && <FileContentDialog vm={vm} editor={editor} setEditor={setEditor} references={activePartition?.key === "config_files" && vm.content ? references.references.get(vm.content.name) : undefined} />}
    {!vm.content && <FileEditorDialog vm={vm} editor={editor} setEditor={setEditor} />}
    <TemplateInstallModal open={installing} onClose={() => setInstalling(false)} onInstalled={() => { void vm.load(); void vm.refresh(); }} />
    </Drawer>
  </Space>;
}
