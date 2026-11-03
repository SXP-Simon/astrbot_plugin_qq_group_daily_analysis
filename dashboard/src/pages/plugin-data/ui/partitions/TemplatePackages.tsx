import { Alert, Button, Empty, Popconfirm, Select, Space, Tag, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { templateCapabilities } from "../../../../entities/report/model/templates";
import type { ManagedFileGroup } from "../../../../entities/plugin-data/api/managedFilesApi";
import { formatBytes } from "../../../../shared/lib/formatters";
import { useTemplatePackages } from "../../model/useTemplatePackages";

export function TemplatePackages({ groups, directory, loading, busy, onSelect, onInstall, onCreate, onRefresh }: {
  groups: ManagedFileGroup[]; directory: string; loading: boolean; busy: boolean; onSelect: (directory: string) => void;
  onInstall: () => void; onCreate: () => void; onRefresh: () => void;
}) {
  const vm = useTemplatePackages(groups, onRefresh);
  const selected = vm.rows.find(item => item.directory === directory);
  const disabled = busy || !!vm.busy;
  const options = vm.rows.map(item => {
    const name = item.directory === "." ? "未归组文件" : item.template?.display_name || item.template?.label || item.directory;
    return { value: item.directory, label: name === item.directory || item.directory === "." ? name : `${name}（${item.directory}）`, searchText: `${name} ${item.directory} ${item.template?.desc || ""}` };
  });
  return <Space direction="vertical" size="middle" style={{ width: "100%" }}>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      <Select aria-label="选择自定义模板" placeholder={`选择模板（共 ${groups.length} 个，可搜索名称或目录）`} value={directory || undefined}
        style={{ flex: "1 1 300px", minWidth: 0 }} showSearch allowClear virtual listHeight={256} loading={loading || vm.loading} disabled={disabled}
        options={options} onChange={value => onSelect(value || "")} filterOption={(input, option) => (option?.searchText || "").toLowerCase().includes(input.toLowerCase())} />
      <Button type="primary" disabled={disabled} onClick={onInstall}>安装模板包</Button>
      {!directory && <Button disabled={disabled} onClick={onCreate}>新建模板源码</Button>}
      <Button icon={<ReloadOutlined />} loading={loading || vm.loading} disabled={disabled} onClick={() => { onRefresh(); void vm.refresh(); }}>刷新模板</Button>
    </div>
    {vm.error && <Alert type="warning" showIcon message={vm.error} description="目录与文件仍可管理；请刷新模板信息后确认渲染能力。" />}
    {selected ? <>
      <Space wrap>
        <Typography.Text copyable>{directory === "." ? "模板分区根目录中的零散文件" : `${directory}/`}</Typography.Text>
        {selected.template && templateCapabilities(selected.template).map(label => <Tag key={label} color="blue">{label}</Tag>)}
        <Typography.Text type="secondary">{selected.count} 个文件 · {formatBytes(selected.size_bytes)}</Typography.Text>
        {directory !== "." && <Popconfirm key={directory} title={`移除模板目录“${directory}”？`}
          description={<Space direction="vertical"><Typography.Text>将移除 {directory}/ 下全部 {selected.count} 个文件及素材（{formatBytes(selected.size_bytes)}），包括当前筛选未显示的文件。</Typography.Text><Typography.Text>使用此模板的配置需重新选择；已生成的报告不受影响。需要保留的源码请先下载。</Typography.Text></Space>}
          okText="移除整个模板" cancelText="取消" onConfirm={async () => { if (await vm.uninstall(directory)) onSelect(""); }}>
          <Button danger disabled={disabled} loading={!!vm.busy}>移除模板</Button>
        </Popconfirm>}
      </Space>
      {directory === "." ? <Alert type="info" showIcon message="这些文件不属于模板包，可在下方逐项或多选删除；不移除整个模板存储根目录。" /> : !selected.template && !vm.loading && !vm.error ? <Alert type="warning" showIcon message="此目录缺少有效的渲染入口，仍可维护文件或整组移除。" description="检查 report.typ、image_template.html 或 html_template.html 等入口文件。" /> : selected.template?.desc && <Typography.Text type="secondary">{selected.template.desc}</Typography.Text>}
    </> : !loading && !groups.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚无自定义模板，可安装模板包或新建源码。" /> : <Typography.Text type="secondary">选择一个模板，管理它的源码与素材；可直接搜索切换，内置模板不在此列表。</Typography.Text>}
  </Space>;
}
