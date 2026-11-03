import { Alert, Button, Input, Popconfirm, Space, Table, Tag, Typography, Upload } from "antd";
import { FileOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons";
import type { ManagedFile, ManagedPartition } from "../../../entities/plugin-data/api/managedFilesApi";
import { partitionPresentation } from "../../../entities/plugin-data/model/partitionPresentation";
import { formatBytes } from "../../../shared/lib/formatters";
import type { useManagedFiles } from "../model/useManagedFiles";
import type { useConfigFileReferences } from "../model/useConfigFileReferences";

export function ManagedFileList({ vm, partition: activePartition, references }: {
  vm: ReturnType<typeof useManagedFiles>; partition: ManagedPartition; references: ReturnType<typeof useConfigFileReferences>;
}) {
  const templatePrefix = activePartition.key === "custom_templates" && vm.directory && vm.directory !== "." ? `${vm.directory}/` : "";
  const fileAction = ["typst_assets", "preview_cache"].includes(activePartition.key) ? "清理" : "删除";
  return <Space direction="vertical" style={{ width: "100%" }}>
            <Space wrap>
              <Input.Search aria-label="搜索文件" placeholder="搜索文件名或相对路径" allowClear onSearch={vm.searchFiles} style={{ width: 260 }} />
              <Button icon={<ReloadOutlined />} loading={vm.loading} onClick={() => { vm.clearSelection(); void vm.load(); void vm.refresh(); void references.refresh(); }}>刷新列表</Button>
              {activePartition.writable && activePartition.key !== "config_files" && <Upload showUploadList={false} beforeUpload={file => { void vm.prepareUpload(file); return false; }}><Button icon={<UploadOutlined />} disabled={vm.busy}>上传文件</Button></Upload>}
              {activePartition.key === "custom_templates" && <Button onClick={() => vm.setEditor({ name: templatePrefix, text: "" })}>新建源码</Button>}
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
          </Space>;
}
