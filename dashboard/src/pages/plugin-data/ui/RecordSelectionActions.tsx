import { Alert, Button, Popconfirm, Space, Typography } from "antd";
import { useRecordSelection } from "../model/useRecordSelection";

export function RecordSelectionActions({ vm, label }: { vm: ReturnType<typeof useRecordSelection>; label: string }) {
  const action = label === "头像缓存" ? "清理" : "删除";
  return <Space direction="vertical" style={{ width: "100%" }}>
    <Space wrap><Typography.Text>已选 {vm.selected.length} 项（最多 200）{vm.busy ? ` · 已处理 ${vm.progress}/${vm.selected.length}` : ""}</Typography.Text>
      <Button size="small" disabled={!vm.selected.length || vm.busy} onClick={vm.clear}>取消选择</Button>
      <Popconfirm title={`${action}所选 ${vm.selected.length} 项${label}？`} description={label === "头像缓存" ? "只移除所选平台缓存键的头像，下次使用时重新获取。不会删除底层数据库文件。" : "只处理已选记录。删除历史版本会修复每日索引；批次或快照删除会影响后续汇总和续跑，正在执行任务的群组会拒绝操作。"} okText={`${action}所选`} cancelText="取消" onConfirm={() => vm.remove()}>
        <Button danger size="small" loading={vm.busy} disabled={!vm.selected.length}>{action}所选</Button>
      </Popconfirm>
    </Space>
    {vm.result && <Alert type={vm.result.failed.length ? "warning" : "success"} showIcon message={`${action}成功 ${vm.result.deleted} 项，失败 ${vm.result.failed.length} 项`} description={vm.result.failed.map((item, index) => <div key={`${item.name}-${index}`}>{item.name}：{item.message}</div>)} />}
  </Space>;
}
