import { useState } from "react";
import { Alert, Button, Card, Col, Descriptions, Drawer, Input, Progress, Row, Select, Space, Statistic, Table, Tabs, Tag, Typography, Upload, message } from "antd";
import { FileOutlined, FolderOpenOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons";
import { FileContentDialog } from "./FileContentDialog";
import { FileEditorDialog, type FileDraft } from "./FileEditorDialog";
import { useManagedFiles } from "../../model/useManagedFiles";
import { formatBytes } from "../../../../shared/lib/formatters";
import { TypstFonts } from "../../../../features/manage-typst-fonts/ui/TypstFonts";
import { TemplateResources } from "../../../../features/manage-template-resources/ui/TemplateResources";
import { TemplateInstallModal } from "../../../../features/install-template/ui/TemplateInstallModal";
import { TEMPLATE_CDN_PRESETS } from "../../../../entities/config/model/renderingConfig";
import type { ManagedFile, ManagedPartition } from "../../../../entities/plugin-data/api/managedFilesApi";

export function ManagedFilesPanel() {
  const vm = useManagedFiles();
  const [editor, setEditor] = useState<FileDraft | null>(null);
  const [installing, setInstalling] = useState(false);
  const [cdn, setCdn] = useState("https://cdn.jsdelivr.net");
  const totalBytes = vm.partitions.reduce((sum, item) => sum + item.size_bytes, 0);
  const totalFiles = vm.partitions.reduce((sum, item) => sum + item.count, 0);

  const activePartition = vm.partitions.find(item => item.key === vm.partition?.key) || vm.partition;

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
        { title: "分区用途与能力", render: (_, item) => <Space direction="vertical" size={2}><Typography.Text>{item.description}</Typography.Text><Space size={0}><Tag color="blue">查看</Tag>{!["state", "avatar_storage"].includes(item.key) && <Tag>导出</Tag>}{item.writable && <Tag color="green">上传 / 替换</Tag>}{item.key === "custom_templates" && <Tag color="purple">源码编辑</Tag>}</Space></Space> },
        { title: "操作", fixed: "right", width: 85, render: (_, item) => <Button type="link" onClick={() => vm.select(item)}>管理</Button> },
      ]} />
    </Card>
    <Drawer open={!!vm.partition} title={vm.partition?.name} width="min(1100px, 96vw)" onClose={() => vm.select(null)} destroyOnClose>
      {activePartition && <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        <Descriptions size="small" column={1} items={[{ key: "path", label: "存储目录", children: <Typography.Text copyable>{activePartition.directory}</Typography.Text> }, { key: "use", label: "用途", children: activePartition.description }]} />
        <Alert showIcon type={activePartition.deletable ? "warning" : "info"} message={activePartition.impact} />
        <Tabs onChange={() => { void vm.load(); void vm.refresh(); }} items={[
          { key: "files", label: "文件列表", children: <Space direction="vertical" style={{ width: "100%" }}>
            <Space wrap>
              <Input.Search aria-label="搜索文件" placeholder="搜索文件名或相对路径" allowClear onSearch={vm.searchFiles} style={{ width: 260 }} />
              <Button icon={<ReloadOutlined />} loading={vm.loading} onClick={() => { void vm.load(); void vm.refresh(); }}>刷新列表</Button>
              {activePartition.writable && <Upload showUploadList={false} beforeUpload={async file => {
                if (file.size > 32 * 1024 * 1024) { void message.error("文件不得超过 32 MiB"); return false; }
                const reader = new FileReader();
                reader.onload = () => { setEditor({ name: file.name, text: "", encoded: String(reader.result).split(",")[1] }); };
                reader.onerror = () => { void message.error("无法读取上传文件"); };
                reader.readAsDataURL(file); return false;
              }}><Button icon={<UploadOutlined />} disabled={vm.busy}>上传文件</Button></Upload>}
              {activePartition.key === "custom_templates" && <><Button onClick={() => setEditor({ name: "", text: "" })}>新建源码</Button><Button type="primary" onClick={() => setInstalling(true)}>安装模板包</Button></>}
            </Space>
            <Table<ManagedFile> rowKey="name" size="small" dataSource={vm.files} loading={vm.loading} scroll={{ x: 650 }} pagination={{ current: vm.page, total: vm.total, pageSize: 20, showSizeChanger: false, onChange: vm.setPage, showTotal: count => `共 ${count} 个文件` }} columns={[
              { title: "文件名", dataIndex: "name", render: name => <Typography.Text style={{ overflowWrap: "anywhere" }}><FileOutlined /> {name}</Typography.Text> },
              { title: "大小", width: 105, render: (_, file) => formatBytes(file.size_bytes) },
              { title: "修改时间", width: 175, render: (_, file) => new Date(file.modified_at * 1000).toLocaleString() },
              { title: "操作", width: 150, render: (_, file) => file.downloadable ? <Button type="link" disabled={vm.busy} onClick={() => void vm.inspect(file.name)}>{file.editable ? "查看 / 编辑" : "查看 / 导出"}</Button> : <Tag>由模块管理</Tag> },
            ]} />
          </Space> },
          ...(activePartition.key === "typst_fonts" ? [{ key: "download", label: "按模板下载", children: <><Select aria-label="字体下载 CDN" value={cdn} options={TEMPLATE_CDN_PRESETS} onChange={setCdn} style={{ width: "100%" }} /><TypstFonts cdnBaseUrl={cdn} /></> }] : []),
          ...(activePartition.key === "template_resources" ? [{ key: "download", label: "按模板下载", children: <TemplateResources cdnBaseUrl={cdn} /> }] : []),
        ]} />
      </Space>}
    </Drawer>
    <FileContentDialog vm={vm} onEdit={setEditor} />
    <FileEditorDialog vm={vm} editor={editor} setEditor={setEditor} />
    <TemplateInstallModal open={installing} onClose={() => setInstalling(false)} onInstalled={() => { void vm.load(); void vm.refresh(); }} />
  </Space>;
}
