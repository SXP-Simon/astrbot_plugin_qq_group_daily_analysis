import { Alert, Button, Card, Empty, Input, List, Popconfirm, Space, Tag, Typography } from "antd";
import { FolderOpenOutlined, ReloadOutlined } from "@ant-design/icons";
import { templateCapabilities } from "../../../../entities/report/model/templates";
import type { ManagedFileGroup } from "../../../../entities/plugin-data/api/managedFilesApi";
import { formatBytes } from "../../../../shared/lib/formatters";
import { useTemplatePackages } from "../../model/useTemplatePackages";

export function TemplatePackages({ groups, loading, onSelect, onInstall, onCreate, onRefresh }: {
  groups: ManagedFileGroup[]; loading: boolean; onSelect: (directory: string) => void;
  onInstall: () => void; onCreate: () => void; onRefresh: () => void;
}) {
  const vm = useTemplatePackages(groups, onRefresh);
  return <Space direction="vertical" size="middle" style={{ width: "100%" }}>
    <Space wrap>
      <Input.Search aria-label="搜索自定义模板" placeholder="搜索模板名称、标识或说明" allowClear onSearch={vm.setSearch} style={{ width: 290 }} />
      <Button type="primary" onClick={onInstall}>安装模板包</Button>
      <Button onClick={onCreate}>新建模板源码</Button>
      <Button icon={<ReloadOutlined />} loading={loading || vm.loading} disabled={!!vm.busy} onClick={() => { onRefresh(); void vm.refresh(); }}>刷新模板</Button>
    </Space>
    <Typography.Text type="secondary">按实际模板目录分组，源码与素材一并维护。进入模板后可搜索、筛选文件类型和多选操作；内置模板不在此列表。</Typography.Text>
    {vm.error && <Alert type="warning" showIcon message={vm.error} description="目录与文件仍可管理；请刷新模板信息后再确认可用状态。" />}
    <List loading={loading || vm.loading} grid={{ gutter: 12, xs: 1, sm: 1, md: 2 }} dataSource={vm.rows}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={vm.search ? "没有匹配的模板" : "尚无自定义模板，可安装模板包或新建源码。"} /> }} renderItem={item => <List.Item>
        <Card size="small" title={<Space><FolderOpenOutlined /><Typography.Text style={{ overflowWrap: "anywhere", whiteSpace: "normal" }}>{item.directory === "." ? "未归组文件" : item.template?.display_name || item.template?.label || item.directory}</Typography.Text></Space>}>
          <Space direction="vertical" style={{ width: "100%" }}>
            <Typography.Text type="secondary" style={{ overflowWrap: "anywhere" }}>{item.directory === "." ? "模板分区根目录" : item.directory}</Typography.Text>
            <Space wrap>{item.template ? templateCapabilities(item.template).map(label => <Tag key={label} color="blue">{label}</Tag>) : <Tag color="warning">{vm.error ? "模板状态未确认" : "未识别为可用模板"}</Tag>}{item.template && <Tag>{item.template.can_uninstall ? "安装包" : "手动管理"}</Tag>}</Space>
            <Typography.Text>{item.template?.desc || (item.directory === "." ? "这些文件不属于模板包，请整理到对应模板目录。" : item.template ? "进入模板维护源码和素材。" : "检查 report.typ、image_template.html 或 html_template.html 等入口文件。")}</Typography.Text>
            <Typography.Text type="secondary">{item.count} 个文件 · {formatBytes(item.size_bytes)}</Typography.Text>
            <Space wrap>
              <Button onClick={() => onSelect(item.directory)} disabled={!!vm.busy}>管理文件</Button>
              {item.template?.can_uninstall && !vm.error && <Popconfirm title={`卸载模板“${item.template.display_name || item.directory}”？`} description="将移除此模板的整个目录及素材，并从可选模板中移除。请先下载需要保留的源码。" okText="卸载" cancelText="取消" onConfirm={() => vm.uninstall(item.directory)}><Button danger loading={vm.busy === item.directory} disabled={!!vm.busy}>卸载模板包</Button></Popconfirm>}
            </Space>
          </Space>
        </Card>
      </List.Item>} />
  </Space>;
}
