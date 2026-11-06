import { useState } from "react";
import { Alert, Button, Card, Input, Radio, Space, Table, Typography } from "antd";
import {
  type ManagedRecordEntry,
  type RecordLocator,
} from "../../../entities/plugin-data/api/managedRecordsApi";
import { formatBytes } from "../../../shared/lib/formatters";
import { useStoredRecords } from "../model/useStoredRecords";
import { useRecordSelection, recordKey } from "../model/useRecordSelection";
import { RecordSelectionActions } from "./RecordSelectionActions";
import { ManagedRecordDialog } from "./ManagedRecordDialog";

export function StoredRecordsTab({ onlyKind }: { onlyKind?: "avatar" | "history" }) {
  const vm = useStoredRecords(onlyKind || "history");
  const { kind, setKind, setSearch, page, setPage, items, total, loading, error, refresh } = vm;
  const [selected, setSelected] = useState<RecordLocator | null>(null);
  const [importing, setImporting] = useState(false);
  const selection = useRecordSelection(
    items.map((item) => item.locator),
    () => void refresh(),
  );
  return (
    <Card size="small" title={kind === "avatar" ? "头像缓存条目" : "分析历史存档"}>
      <Space direction="vertical" style={{ width: "100%" }}>
        <Space wrap>
          {!onlyKind && (
            <Radio.Group
              value={kind}
              onChange={(event) => {
                setKind(event.target.value);
                setPage(1);
                selection.clear();
              }}
              options={[
                { label: "分析历史 (KV)", value: "history" },
                { label: "头像缓存条目", value: "avatar" },
              ]}
            />
          )}
          <Input.Search
            aria-label="搜索业务记录"
            placeholder="搜索群号、日期或缓存键"
            onSearch={(value) => {
              setSearch(value);
              setPage(1);
              selection.clear();
            }}
            allowClear
            style={{ width: 250 }}
          />
          <Button loading={loading} onClick={() => void refresh()}>
            刷新记录
          </Button>
          {kind === "history" && <Button onClick={() => setImporting(true)}>导入历史记录</Button>}
        </Space>
        <Typography.Text type="secondary">
          {kind === "history"
            ? "此处展示本插件 KV 中的完整分析存档，包含摘要和重绘所需数据；每日指针不作为重复记录展示。"
            : "按真实平台缓存键管理头像；磁盘占用见存储概览，列表不会加载所有图片。"}
        </Typography.Text>
        {error && <Alert type="error" message={error} showIcon />}
        <RecordSelectionActions
          vm={selection}
          label={kind === "history" ? "分析存档" : "头像缓存"}
        />
        <Table<ManagedRecordEntry>
          rowKey={(item) => recordKey(item.locator)}
          rowSelection={{
            selectedRowKeys: selection.keys,
            onChange: selection.select,
            preserveSelectedRowKeys: true,
            getCheckboxProps: () => ({ disabled: selection.busy }),
          }}
          dataSource={items}
          size="small"
          loading={loading}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            showSizeChanger: false,
            onChange: setPage,
          }}
          columns={[
            {
              title: "记录标识",
              dataIndex: "name",
              render: (name) => (
                <Typography.Text style={{ overflowWrap: "anywhere" }}>{name}</Typography.Text>
              ),
            },
            ...(kind === "history"
              ? [
                  {
                    title: "群组",
                    render: (_: unknown, item: ManagedRecordEntry) => item.locator.group_id || "—",
                  },
                ]
              : []),
            {
              title: "数据大小",
              render: (_, item) => (kind === "avatar" ? "按需加载" : formatBytes(item.size_bytes)),
            },
            {
              title: "操作",
              render: (_, item) => (
                <Button type="link" onClick={() => setSelected(item.locator)}>
                  {kind === "avatar" ? "预览 / 管理" : "查看 / 管理"}
                </Button>
              ),
            },
          ]}
        />
        <ManagedRecordDialog
          locator={selected}
          importKind={importing ? "history" : undefined}
          onClose={() => {
            setSelected(null);
            setImporting(false);
          }}
          onChanged={() => void refresh()}
        />
      </Space>
    </Card>
  );
}
