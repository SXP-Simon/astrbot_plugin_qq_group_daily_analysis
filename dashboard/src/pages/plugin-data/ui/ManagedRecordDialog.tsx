import { Alert, Button, Image, Input, Modal, Popconfirm, Space, Spin, Typography } from "antd";
import { useManagedRecord } from "../model/useManagedRecord";
import type { RecordLocator } from "../../../entities/plugin-data/api/managedRecordsApi";

export function ManagedRecordDialog({
  locator,
  importKind,
  onClose,
  onChanged,
}: {
  locator: RecordLocator | null;
  importKind?: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const vm = useManagedRecord(locator, onChanged, onClose, importKind);
  const kind = locator?.kind || importKind;
  const avatar =
    vm.record?.data &&
    typeof vm.record.data === "object" &&
    !Array.isArray(vm.record.data) &&
    "data_uri" in vm.record.data
      ? vm.record.data.data_uri
      : null;
  return (
    <Modal
      open={!!locator || !!importKind}
      title={
        kind === "avatar" ? "头像缓存详情" : importKind ? "导入业务记录" : "业务记录详情与修订"
      }
      width={kind === "avatar" ? 560 : 900}
      onCancel={() => {
        if (!vm.busy) onClose();
      }}
      footer={
        <Space wrap>
          <Button disabled={!vm.record} onClick={vm.download}>
            {kind === "avatar" ? "下载头像图片" : "导出完整 JSON"}
          </Button>
          {!importKind && kind !== "avatar" && (
            <Button disabled={!vm.record || vm.busy} onClick={() => vm.setEditing(!vm.editing)}>
              {vm.editing ? "退出编辑" : "编辑产物"}
            </Button>
          )}
          {vm.editing && (
            <Button
              type="primary"
              loading={vm.busy}
              onClick={() => void vm.save(importKind ? "create" : "replace")}
            >
              {importKind ? "导入为新记录" : "保存修订"}
            </Button>
          )}
          {!importKind && (
            <Popconfirm
              title={kind === "avatar" ? "清除此头像缓存？" : "删除此业务记录？"}
              description={
                kind === "avatar"
                  ? "仅移除此平台缓存键的头像，下次需要时重新获取。"
                  : "此操作会影响历史查阅、批次汇总或断点续跑，请先导出留存。"
              }
              onConfirm={() => vm.save("delete")}
            >
              <Button danger disabled={!vm.record} loading={vm.busy}>
                {kind === "avatar" ? "清除此头像缓存" : "删除此记录"}
              </Button>
            </Popconfirm>
          )}
          <Button onClick={onClose} disabled={vm.busy}>
            关闭
          </Button>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: "100%" }}>
        <Alert
          type="warning"
          showIcon
          message={
            kind === "avatar"
              ? "头像缓存删除后将按需重新获取；数据库文件保持完整。"
              : kind === "checkpoint"
                ? "只修改 data 内的阶段产物。任务归属、创建时间和有效期不可修改，错误内容可能影响断点续跑。"
                : kind === "batch"
                  ? "修改批次会影响后续汇总，保存不会移动消息游标。请保持群组、批次身份及各计数与原消息一致。"
                  : "管理分析历史 KV 存档；删除最新版本会回退每日索引。操作不删除报告图片或 Trace 统计。"
          }
        />
        {importKind && (
          <Typography.Text>
            粘贴此前导出的完整 JSON（locator +
            data），导入不会覆盖已存在的记录。快照由分析任务创建，不提供新建入口。
          </Typography.Text>
        )}
        {vm.error && <Alert type="error" showIcon message={vm.error} />}
        {kind === "avatar" && <Typography.Text copyable>{locator?.key}</Typography.Text>}
        {vm.busy && !vm.record ? (
          <Spin />
        ) : kind === "avatar" ? (
          typeof avatar === "string" && avatar.startsWith("data:image/") ? (
            <Image src={avatar} width={160} />
          ) : (
            <Alert type="info" message="暂无可预览的头像，请刷新条目后重试。" />
          )
        ) : (
          <Input.TextArea
            aria-label="业务记录 JSON"
            value={vm.text}
            readOnly={!vm.editing}
            onChange={(event) => vm.setText(event.target.value)}
            rows={22}
            spellCheck={false}
          />
        )}
      </Space>
    </Modal>
  );
}
