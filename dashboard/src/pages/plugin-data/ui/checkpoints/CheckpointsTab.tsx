import React from "react";
import {
  Card,
  Table,
  Button,
  Popconfirm,
  Tag,
  Typography,
  Space,
  Tooltip,
  Empty,
  theme,
} from "antd";
import {
  DeleteOutlined,
  EyeOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { formatBytes, formatTimestamp } from "../../../../shared/lib/formatters";
import { CheckpointItem } from "../../../../entities/plugin-data/model/types";
import { usePluginDataViewModel } from "../../model/usePluginDataViewModel";
import { SANS_NUM_STYLE, getStageMeta } from "../constants";
import { CheckpointFilterBar } from "./CheckpointFilterBar";

const { Text } = Typography;

interface CheckpointsTabProps {
  vm: ReturnType<typeof usePluginDataViewModel>;
}

export const CheckpointsTab: React.FC<CheckpointsTabProps> = ({ vm }) => {
  const { token } = theme.useToken();
  const {
    checkpoints,
    checkpointsTotal,
    checkpointsPage,
    checkpointsPageSize,
    loadingCheckpoints,
    ckptFilterGroup,
    ckptFilterDate,
    ckptFilterStage,
  } = vm;

  const ckptColumns = [
    {
      title: "群聊号码",
      dataIndex: "group_id",
      key: "group_id",
      width: 130,
      render: (gid: string) => (
        <Text strong style={{ fontSize: 13 }}>
          {gid}
        </Text>
      ),
    },
    {
      title: "分析归属日期",
      dataIndex: "date_str",
      key: "date_str",
      width: 120,
      render: (d: string) => (
        <Tag color="cyan" style={{ fontSize: 12, ...SANS_NUM_STYLE }}>
          {d}
        </Tag>
      ),
    },
    {
      title: "流水线阶段 (Stage)",
      dataIndex: "stage_name",
      key: "stage_name",
      width: 240,
      render: (stage: string) => {
        const meta = getStageMeta(stage);
        return (
          <Tooltip title={`底层阶段标识: ${stage}`}>
            <Tag color={meta.color} style={{ fontSize: 12, margin: 0 }}>
              {meta.label} ({stage})
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: "任务 Trace ID",
      dataIndex: "trace_id",
      key: "trace_id",
      width: 180,
      render: (tid: string) => {
        if (!tid) {
          return (
            <Tooltip title="历史通用快照 (未关联特定任务 ID)">
              <Tag color="default" style={{ fontSize: 11, margin: 0 }}>
                Legacy (按天快照)
              </Tag>
            </Tooltip>
          );
        }
        return (
          <Tooltip title={`完整任务 Trace ID: ${tid}`}>
            <Tag
              color="geekblue"
              style={{ fontSize: 11, margin: 0, ...SANS_NUM_STYLE }}
            >
              {tid.length > 14 ? `${tid.slice(0, 14)}...` : tid}
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: "快照大小",
      key: "data_size",
      width: 100,
      align: "right" as const,
      render: (_: unknown, row: CheckpointItem) => {
        const bytes = row.data_size_bytes ?? row.data_size ?? 0;
        return <span style={SANS_NUM_STYLE}>{formatBytes(bytes)}</span>;
      },
    },
    {
      title: "快照写入时间",
      key: "created_at",
      width: 170,
      render: (_: unknown, row: CheckpointItem) => {
        if (row.created_at_formatted) {
          return (
            <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
              {row.created_at_formatted}
            </span>
          );
        }
        if (typeof row.created_at === "number") {
          return (
            <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
              {formatTimestamp(row.created_at)}
            </span>
          );
        }
        return (
          <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
            {row.created_at || row.updated_at || "-"}
          </span>
        );
      },
    },
    {
      title: "操作",
      key: "action",
      width: 140,
      align: "center" as const,
      render: (_: unknown, item: CheckpointItem) => (
        <Space size={4}>
          <Button
            size="small"
            type="text"
            icon={<EyeOutlined />}
            onClick={() => vm.handleOpenCkptDetail(item)}
            style={{ fontSize: 12 }}
          >
            产物 JSON
          </Button>
          <Popconfirm
            title="确认删除该阶段快照？"
            description="删除后将无法基于此阶段进行断点续跑或零Token重绘。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true, size: "small" }}
            cancelButtonProps={{ size: "small" }}
            onConfirm={() =>
              vm.handleDeleteCheckpoint(
                item.group_id,
                item.date_str,
                item.stage_name,
                item.trace_id
              )
            }
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
      {/* 筛选栏 */}
      <CheckpointFilterBar vm={vm} />

      {/* Checkpoint 列表 */}
      <Card
        size="small"
        title={
          <Space size={8}>
            <SaveOutlined style={{ color: "#2563eb" }} />
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              阶段产物快照 (Checkpoint) 列表
            </span>
            <Tag color="blue" style={{ fontSize: 11 }}>
              共 {checkpointsTotal} 条记录
            </Tag>
          </Space>
        }
      >
        <Table<CheckpointItem>
          rowKey={(r) =>
            r.checkpoint_id ||
            `${r.group_id}_${r.date_str}_${r.stage_name}_${r.trace_id || ""}`
          }
          columns={ckptColumns}
          dataSource={checkpoints}
          loading={loadingCheckpoints}
          size="small"
          scroll={{ x: 1050 }}
          pagination={{
            current: checkpointsPage,
            pageSize: checkpointsPageSize,
            total: checkpointsTotal,
            showSizeChanger: true,
            showQuickJumper: true,
            pageSizeOptions: ["10", "20", "50", "100"],
            showTotal: (total) => `共 ${total} 条快照`,
            onChange: (page, pageSize) => {
              vm.loadCheckpoints(
                page,
                pageSize,
                ckptFilterGroup,
                ckptFilterDate,
                ckptFilterStage
              );
            },
          }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无阶段快照记录（任务成功完成或未开启 Checkpoint）"
              />
            ),
          }}
        />
      </Card>
    </Space>
  );
};
