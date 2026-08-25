import React from "react";
import { Table, Tag, Tooltip, Progress, Button, Skeleton, Empty } from "antd";
import type { TablePaginationConfig } from "antd/es/table";
import type { FilterValue, SorterResult } from "antd/es/table/interface";
import { EyeOutlined } from "@ant-design/icons";
import { TraceRecord } from "../../entities/trace/model/types";
import { StatusTag } from "../../shared/ui/StatusTag";
import { TriggerTypeTag } from "../../shared/ui/TriggerTypeTag";
import { formatDuration, formatTokens, formatTimestamp } from "../../shared/lib/formatters";

interface TraceTableProps {
  traces: TraceRecord[];
  total: number;
  loading: boolean;
  page: number;
  pageSize: number;
  onViewTrace: (traceId: string) => void;
  onTableChange: (
    pagination: TablePaginationConfig,
    filters: Record<string, FilterValue | null>,
    sorter: SorterResult<TraceRecord> | SorterResult<TraceRecord>[]
  ) => void;
}

export const TraceTable: React.FC<TraceTableProps> = ({
  traces,
  total,
  loading,
  page,
  pageSize,
  onViewTrace,
  onTableChange,
}) => {
  const columns = [
    {
      title: "任务编号",
      dataIndex: "trace_id",
      key: "trace_id",
      width: 170,
      render: (id: string) => (
        <a
          className="font-mono text-xs font-semibold"
          onClick={() => onViewTrace(id)}
        >
          {id}
        </a>
      ),
    },
    {
      title: "群聊",
      dataIndex: "group_id",
      key: "group_id",
      render: (gid: string, r: TraceRecord) => {
        const p = !r.platform || r.platform === "auto" || r.platform === "default" ? "" : r.platform;
        return (
          <Tooltip title={`群号: ${gid}${p ? ` | 平台: ${p}` : ""}`}>
            <span className="font-mono text-xs">
              {r.group_name || "未知群"} ({gid})
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: "平台",
      dataIndex: "platform",
      key: "platform",
      width: 80,
      render: (p: string) => {
        const displayP = !p || p === "auto" || p === "default" ? "-" : p;
        return <Tag>{displayP}</Tag>;
      },
    },
    {
      title: "触发方式",
      dataIndex: "trigger_type",
      key: "trigger_type",
      width: 100,
      render: (t: string) => <TriggerTypeTag triggerType={t} />,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 105,
      render: (st: string) => <StatusTag status={st} />,
    },
    {
      title: "耗时",
      dataIndex: "duration_ms",
      key: "duration_ms",
      width: 95,
      sorter: true,
      render: (dur?: number) => (
        <span className="font-mono text-xs font-semibold" style={{ color: "#1677ff" }}>
          {formatDuration(dur)}
        </span>
      ),
    },
    {
      title: "模型消耗",
      dataIndex: "total_tokens",
      key: "total_tokens",
      width: 95,
      sorter: true,
      render: (t?: number) => (
        <span className="font-mono text-xs">
          {formatTokens(t)}
        </span>
      ),
    },
    {
      title: "消息留存率",
      dataIndex: "compression_ratio",
      key: "compression_ratio",
      width: 120,
      sorter: true,
      render: (ratio: number | undefined, r: TraceRecord) => {
        if (ratio === undefined || ratio === null) return <span className="text-xs">-</span>;
        const pct = Math.round(ratio * 100);
        return (
          <Tooltip title={`读取: ${r.raw_message_count || 0}条 / 有效: ${r.cleaned_message_count || 0}条`}>
            <Progress percent={pct} size="small" style={{ width: 80 }} />
          </Tooltip>
        );
      },
    },
    {
      title: "开始时间",
      dataIndex: "started_at",
      key: "started_at",
      width: 165,
      sorter: true,
      defaultSortOrder: "descend" as const,
      render: (ts: number) => (
        <Tooltip title={`记录时间戳: ${ts}`}>
          <span className="font-mono text-xs">
            {formatTimestamp(ts)}
          </span>
        </Tooltip>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 80,
      render: (_value: unknown, r: TraceRecord) => (
        <Button
          size="small"
          type="link"
          icon={<EyeOutlined />}
          onClick={() => onViewTrace(r.trace_id)}
        >
          详情
        </Button>
      ),
    },
  ];

  if (loading && traces.length === 0) {
    return (
      <div style={{ padding: "24px 12px", minHeight: 460 }}>
        <Skeleton
          active
          paragraph={{
            rows: 8,
            width: ["100%", "95%", "90%", "100%", "92%", "96%", "85%", "70%"],
          }}
        />
      </div>
    );
  }

  return (
    <div style={{ minHeight: 460 }}>
      {traces.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无符合条件的分析记录"
          style={{ margin: "64px 0" }}
        />
      ) : (
        <Table
          size="small"
          columns={columns}
          dataSource={traces}
          rowKey="trace_id"
          loading={loading}
          onChange={onTableChange}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            pageSizeOptions: ["10", "15", "20", "50", "100"],
            showTotal: (t) => `共 ${t} 条记录`,
          }}
        />
      )}
    </div>
  );
};
