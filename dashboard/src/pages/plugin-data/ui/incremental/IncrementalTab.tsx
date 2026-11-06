import { ManagedRecordDialog } from "../ManagedRecordDialog";
import { RecordSelectionActions } from "../RecordSelectionActions";
import { useRecordSelection, recordKey } from "../../model/useRecordSelection";
import type { RecordLocator } from "../../../../entities/plugin-data/api/managedRecordsApi";
import React, { useEffect, useState } from "react";
import {
  Card,
  Row,
  Col,
  Table,
  Button,
  Popconfirm,
  Tag,
  Typography,
  Space,
  Select,
  Tooltip,
  Badge,
  Empty,
  theme,
} from "antd";
import {
  DeleteOutlined,
  ReloadOutlined,
  EyeOutlined,
  ClearOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { formatTimestamp, formatTokens } from "../../../../shared/lib/formatters";
import { IncrementalBatchItem } from "../../../../entities/plugin-data/model/types";
import { usePluginDataViewModel } from "../../model/usePluginDataViewModel";
import { SANS_NUM_STYLE } from "../constants";
import { IncrementalCursorCards } from "./IncrementalCursorCards";

const { Text } = Typography;

interface IncrementalTabProps {
  vm: ReturnType<typeof usePluginDataViewModel>;
}

export const IncrementalTab: React.FC<IncrementalTabProps> = ({ vm }) => {
  const [managedLocator, setManagedLocator] = useState<RecordLocator | null>(null);
  const [importing, setImporting] = useState(false);
  const { token } = theme.useToken();
  const { incrGroups, selectedIncrGroup, incrBatches, incrCursor, loadingIncremental } = vm;

  const selection = useRecordSelection(
    vm.incrBatches.map((item) => ({
      kind: "batch",
      group_id: item.group_id,
      batch_id: item.batch_id,
    })),
    () => {
      void vm.refreshIncrGroups();
      void vm.loadIncrementalData(vm.selectedIncrGroup);
    },
  );
  const clearSelection = selection.clear;
  useEffect(() => {
    clearSelection();
  }, [vm.selectedIncrGroup, clearSelection]);
  const batchColumns = [
    {
      title: "批次 ID",
      dataIndex: "batch_id",
      key: "batch_id",
      width: 170,
      render: (batchId: string) => {
        if (!batchId) return "-";
        return (
          <Tooltip title={`完整批次 ID: ${batchId}`}>
            <Tag
              color="blue"
              style={{
                ...SANS_NUM_STYLE,
                fontWeight: 500,
                fontSize: 12,
                margin: 0,
                maxWidth: 140,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                display: "inline-block",
                verticalAlign: "middle",
              }}
            >
              {batchId.length > 14 ? `${batchId.slice(0, 14)}...` : batchId}
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: "生成时间",
      dataIndex: "timestamp",
      key: "timestamp",
      width: 170,
      render: (ts: number) => (
        <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
          <ClockCircleOutlined style={{ marginRight: 4 }} />
          {formatTimestamp(ts)}
        </span>
      ),
    },
    {
      title: "消息数 / 字符",
      key: "msg_stats",
      width: 140,
      render: (_: unknown, item: IncrementalBatchItem) => (
        <Space size={4}>
          <Badge
            count={item.messages_count}
            overflowCount={999999}
            style={{ backgroundColor: "#1677ff", fontSize: 11 }}
          />
          <Text type="secondary" style={{ fontSize: 11 }}>
            ({(item.characters_count || 0).toLocaleString()} 字)
          </Text>
        </Space>
      ),
    },
    {
      title: "提炼话题概览",
      dataIndex: "topics",
      key: "topics",
      ellipsis: true,
      render: (topics: IncrementalBatchItem["topics"]) => {
        if (!topics || topics.length === 0) {
          return (
            <Text type="secondary" style={{ fontSize: 12 }}>
              无提炼话题
            </Text>
          );
        }
        return (
          <Space wrap size={[4, 4]}>
            {topics.map((t, idx) => (
              <Tag
                key={idx}
                color={
                  (t.heat_score || 0) >= 80
                    ? "volcano"
                    : (t.heat_score || 0) >= 50
                      ? "orange"
                      : "geekblue"
                }
                style={{
                  fontSize: 11,
                  maxWidth: 180,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {t.title || "未命名话题"} ({t.heat_score || 0}℃)
              </Tag>
            ))}
          </Space>
        );
      },
    },
    {
      title: "Token 消耗",
      key: "token_usage",
      width: 120,
      render: (_: unknown, item: IncrementalBatchItem) => {
        const total = item.token_usage?.total_tokens;
        return <span style={SANS_NUM_STYLE}>{total ? formatTokens(total) : "-"}</span>;
      },
    },
    {
      title: "操作",
      key: "action",
      width: 140,
      align: "center" as const,
      render: (_: unknown, item: IncrementalBatchItem) => (
        <Space size={4}>
          <Button
            size="small"
            type="text"
            icon={<EyeOutlined />}
            onClick={() => vm.handleOpenBatchDetail(item)}
            style={{ fontSize: 12 }}
          >
            详情
          </Button>
          <Button
            size="small"
            type="link"
            onClick={() =>
              setManagedLocator({ kind: "batch", group_id: item.group_id, batch_id: item.batch_id })
            }
          >
            管理
          </Button>
          <Popconfirm
            title="确认删除该增量批次？"
            description="删除后该批次的话题与统计数据将不再参与汇总计算。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true, size: "small" }}
            cancelButtonProps={{ size: "small" }}
            onConfirm={() => vm.handleDeleteBatch(item.group_id, item.batch_id)}
          >
            <Button
              size="small"
              type="text"
              danger
              icon={<DeleteOutlined />}
              style={{ fontSize: 12 }}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {/* 群号选择与操作栏 */}
      <Card size="small">
        <Row justify="space-between" align="middle" gutter={[8, 8]}>
          <Col>
            <Space size={12} wrap>
              <Text strong style={{ fontSize: 13 }}>
                选择目标群号:
              </Text>
              <Select
                style={{ width: 220 }}
                value={selectedIncrGroup || undefined}
                placeholder="请选择含有增量数据的群"
                onChange={vm.handleSelectIncrGroup}
                loading={loadingIncremental}
                options={incrGroups.map((g) => ({
                  label: `群: ${g}`,
                  value: g,
                }))}
              />
              <Button
                size="small"
                icon={<ReloadOutlined spin={loadingIncremental} />}
                onClick={() => {
                  vm.refreshIncrGroups();
                  if (selectedIncrGroup) {
                    vm.loadIncrementalData(selectedIncrGroup);
                  }
                }}
              >
                刷新
              </Button>
            </Space>
          </Col>

          <Col>
            {selectedIncrGroup && (
              <Popconfirm
                title={`确认重置群「${selectedIncrGroup}」的所有增量批次？`}
                description="此操作将清空该群全部已存储增量 Batch，并将分析游标时间戳重置为 0，下次触发将重新全量拉取分析。"
                okText="确认重置"
                cancelText="取消"
                okButtonProps={{ danger: true, size: "small" }}
                cancelButtonProps={{ size: "small" }}
                onConfirm={() => vm.handleResetIncrGroup(selectedIncrGroup)}
              >
                <Button danger size="small" type="primary" ghost icon={<ClearOutlined />}>
                  重置本群增量状态
                </Button>
              </Popconfirm>
            )}
          </Col>
        </Row>
      </Card>

      {/* 游标状态卡片 */}
      {selectedIncrGroup && incrCursor && (
        <IncrementalCursorCards cursor={incrCursor} batchCount={incrBatches.length} />
      )}

      {/* 批次明细表格 */}
      <Card
        size="small"
        title={
          <Space size={8}>
            <ThunderboltOutlined style={{ color: "#1677ff" }} />
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              {selectedIncrGroup ? `群「${selectedIncrGroup}」暂存增量批次明细` : "增量批次明细"}
            </span>
            {incrBatches.length > 0 && (
              <Tag color="blue" style={{ fontSize: 11 }}>
                {incrBatches.length} 个批次
              </Tag>
            )}
          </Space>
        }
      >
        <Button style={{ marginBottom: 12 }} onClick={() => setImporting(true)}>
          导入 / 新建增量批次
        </Button>
        <ManagedRecordDialog
          locator={managedLocator}
          importKind={importing ? "batch" : undefined}
          onClose={() => {
            setManagedLocator(null);
            setImporting(false);
          }}
          onChanged={() => {
            void vm.refreshIncrGroups();
            void vm.loadIncrementalData(vm.selectedIncrGroup);
          }}
        />
        {selectedIncrGroup ? (
          <>
            <Space direction="vertical" style={{ width: "100%", marginBottom: 12 }}>
              <RecordSelectionActions vm={selection} label="增量批次" />
            </Space>
            <Table<IncrementalBatchItem>
              rowKey={(item) =>
                recordKey({ kind: "batch", group_id: item.group_id, batch_id: item.batch_id })
              }
              rowSelection={{
                selectedRowKeys: selection.keys,
                onChange: selection.select,
                preserveSelectedRowKeys: true,
                getCheckboxProps: () => ({ disabled: selection.busy }),
              }}
              columns={batchColumns}
              dataSource={incrBatches}
              pagination={false}
              size="small"
              scroll={{ x: 1000 }}
              loading={loadingIncremental}
              locale={{
                emptyText: (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="当前群暂无增量批次数据（已汇总为日报或尚未触发增量任务）"
                  />
                ),
              }}
            />
          </>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="请在上方选择群号以查看其增量分析批次"
          />
        )}
      </Card>
    </Space>
  );
};
