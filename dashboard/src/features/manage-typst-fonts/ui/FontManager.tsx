import { useState } from "react";
import { Alert, Button, Input, Modal, Popconfirm, Select, Space, Table, Tag, Tooltip, Typography, Upload } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useManagedFonts, type ManagedFontRow } from "../model/useManagedFonts";
import { KNOWN_TEMPLATES } from "../../../entities/report/model/templates";
import { DEFAULT_TEMPLATE_CDN_BASE_URL, TEMPLATE_CDN_PRESETS } from "../../../entities/config/model/renderingConfig";
import { formatBytes } from "../../../shared/lib/formatters";

export function FontManager({ onChanged }: { onChanged: () => void }) {
  const vm = useManagedFonts(onChanged);
  const [cdn, setCdn] = useState(DEFAULT_TEMPLATE_CDN_BASE_URL);
  const [replacement, setReplacement] = useState<{ file: File; existing: ManagedFontRow } | null>(null);
  const disabled = vm.loading || vm.busy;
  const themeName = (key: string) => KNOWN_TEMPLATES.find(item => item.key === key)?.name || key;
  const selectedFiles = vm.files.filter(file => vm.selected.includes(file.name));
  const affected = vm.groups.filter(group => selectedFiles.some(file => group.required.includes(file.name)));

  return <Space direction="vertical" size="middle" style={{ width: "100%" }}>
    <Typography.Text>按模板检查缺失字体并补齐；共享字体只保存一份。替换或移除会影响所有依赖该字体的模板。</Typography.Text>
    <Space wrap>
      <Select aria-label="管理字体的模板" value={vm.theme} disabled={disabled} style={{ minWidth: 260 }} onChange={vm.selectTheme} options={[{ value: "__all__", label: "全部预设与自定义字体" }, ...vm.groups.map(group => ({ value: group.theme, label: themeName(group.theme) }))]} />
      <Select aria-label="字体下载 CDN" value={cdn} disabled={disabled} options={TEMPLATE_CDN_PRESETS} onChange={setCdn} style={{ width: 350, maxWidth: "100%" }} />
      <Button type="primary" disabled={disabled || !vm.status || !vm.missing} loading={vm.busy} onClick={() => void vm.download(cdn)}>{vm.theme === "__all__" ? "补齐全部预设字体" : "补齐所选模板字体"}</Button>
      <Button disabled={vm.busy} loading={vm.loading} onClick={() => void vm.refresh()}>刷新字体状态</Button>
    </Space>
    {vm.status && <Alert type={vm.missing ? "info" : "success"} showIcon message={`已安装 ${vm.installed} / ${vm.required} 个字体${vm.missing ? `，缺少 ${vm.missing} 个` : "，已就绪"}`} />}
    {vm.error && <Alert type="error" showIcon message={vm.error} />}
    <Space wrap>
      <Input.Search aria-label="搜索字体" placeholder="搜索字体文件名" allowClear onSearch={vm.searchFonts} disabled={disabled} style={{ width: 250 }} />
      <Select aria-label="字体格式筛选" value={vm.format} onChange={vm.filterFormat} disabled={disabled} style={{ width: 150 }} options={[{ value: "", label: "全部字体格式" }, ...["ttf", "otf", "ttc"].map(value => ({ value, label: value.toUpperCase() }))]} />
      <Upload accept=".ttf,.otf,.ttc" showUploadList={false} disabled={disabled} beforeUpload={async file => {
        const existing = vm.files.find(item => item.name === file.name);
        if (existing) setReplacement({ file, existing: { name: existing.name, file: existing, themes: vm.groups.filter(group => group.required.includes(existing.name)).map(group => group.theme) } });
        else await vm.upload(file);
        return false;
      }}><Button icon={<UploadOutlined />} disabled={disabled}>上传字体</Button></Upload>
      <Popconfirm title={`移除所选的 ${selectedFiles.length} 个字体？`} description={affected.length ? `将影响：${affected.map(group => themeName(group.theme)).join("、")}。移除后可按模板重新补齐。` : "自定义字体移除后，需要手动重新上传才能使用。"} okText="移除字体" cancelText="取消" onConfirm={() => vm.remove(selectedFiles)}>
        <Button danger disabled={disabled || !selectedFiles.length}>移除所选（{selectedFiles.length}）</Button>
      </Popconfirm>
    </Space>
    {vm.removed && <Alert type={vm.removed.failed.length ? "warning" : "success"} showIcon message={`已移除 ${vm.removed.deleted.length} 个字体，失败 ${vm.removed.failed.length} 个`} description={vm.removed.failed.map(file => <div key={file.name}>{file.name}：{file.message}</div>)} />}
    <Table<ManagedFontRow> rowKey="name" size="small" dataSource={vm.rows} loading={vm.loading} scroll={{ x: 700 }} pagination={{ pageSize: 15, showSizeChanger: false }} rowSelection={{ selectedRowKeys: vm.selected, onChange: keys => vm.setSelected(keys.map(String)), getCheckboxProps: row => ({ disabled: disabled || !row.file }) }} columns={[
      { title: "字体文件", dataIndex: "name", width: 210, render: name => <Typography.Text style={{ overflowWrap: "anywhere" }}>{name}</Typography.Text> },
      { title: "安装状态", width: 95, render: (_, row) => <Tag color={row.file ? "success" : "default"}>{row.file ? "已安装" : "缺失"}</Tag> },
      { title: "大小", width: 100, render: (_, row) => row.file ? formatBytes(row.file.size_bytes) : "—" },
      { title: "依赖模板", render: (_, row) => !row.themes.length ? <Typography.Text type="secondary">自定义字体，供自定义模板使用</Typography.Text> : row.themes.length === vm.groups.length ? <Tooltip title={row.themes.map(themeName).join("、")}><Tag color="blue">所有内置模板共享</Tag></Tooltip> : <Space size={0} wrap>{row.themes.map(key => <Tag key={key}>{themeName(key)}</Tag>)}</Space> },
      { title: "操作", width: 145, render: (_, row) => row.file ? <Space size={4}>
        <Upload accept=".ttf,.otf,.ttc" showUploadList={false} disabled={disabled} beforeUpload={file => { setReplacement({ file, existing: row }); return false; }}><Button type="link" size="small" disabled={disabled}>替换</Button></Upload>
        <Popconfirm title={`移除 ${row.name}？`} description={row.themes.length ? `将影响 ${row.themes.length} 个模板；下次渲染可能使用回退字体，排版可能变化。` : "自定义模板使用的字体需要手动重新上传。"} okText="移除" cancelText="取消" onConfirm={() => { if (row.file) return vm.remove([row.file]); }}><Button type="link" danger size="small" disabled={disabled}>移除</Button></Popconfirm>
      </Space> : <Typography.Text type="secondary">通过上方按钮补齐</Typography.Text> },
    ]} />
    <Typography.Text type="secondary">预设字体由多个模板共享。自定义字体也保存在插件 data 目录；模板需填写字体内部的字体族名称，文件名不代表字体族。</Typography.Text>
    <Modal open={!!replacement} title="替换字体" okText="确认替换" cancelText="取消" confirmLoading={vm.busy} onCancel={() => { if (!vm.busy) setReplacement(null); }} onOk={async () => {
      if (replacement && await vm.upload(replacement.file, replacement.existing.file)) setReplacement(null);
    }}>
      {replacement && <Space direction="vertical" style={{ width: "100%" }}>
        <Typography.Text>用 {replacement.file.name} 替换 {replacement.existing.name}，保留原文件名。</Typography.Text>
        <Alert type="warning" showIcon message="请选择同一字体族的正确版本" description={replacement.existing.themes.length ? `将影响：${replacement.existing.themes.map(themeName).join("、")}` : "将影响引用此字体的自定义模板"} />
        {vm.error && <Alert type="error" message={vm.error} />}
      </Space>}
    </Modal>
  </Space>;
}
