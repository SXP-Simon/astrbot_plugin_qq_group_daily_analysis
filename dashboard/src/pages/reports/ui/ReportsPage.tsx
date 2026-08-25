import React from "react";
import { Card, Table, Empty, Button, Tag, Typography, Space, Tooltip, Skeleton } from "antd";
import {
  FileImageOutlined,
  FileTextOutlined,
  EyeOutlined,
  DownloadOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { formatTimestamp } from "../../../shared/lib/formatters";
import { useReportsViewModel } from "../model/useReportsViewModel";
import { ReportItem } from "../../../entities/report/model/types";
import { ReportPreviewModal } from "../../../widgets/report-preview-modal/ReportPreviewModal";
import { ReportFilterBar } from "../../../features/filter-reports/ui/ReportFilterBar";

const { Text, Paragraph } = Typography;

interface ReportsPageProps {
  viewModel: ReturnType<typeof useReportsViewModel>;
  onViewTrace?: (traceId: string) => void;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({ viewModel, onViewTrace }) => {
  const {
    reports,
    rawReports,
    groups,
    loading,
    search,
    setSearch,
    selectedGroup,
    setSelectedGroup,
    setDateRange,
    refresh,
    previewOpen,
    previewLoading,
    selectedReport,
    openPreview,
    closePreview,
    downloadReport,
  } = viewModel;

  const columns = [
    {
      title: "报告文件",
      dataIndex: "filename",
      key: "filename",
      width: 240,
      ellipsis: true,
      render: (fn: string, r: ReportItem) => {
        const isHtml = Boolean(
          r.is_html ||
            fn.toLowerCase().endsWith(".html") ||
            fn.toLowerCase().endsWith(".htm")
        );
        return (
          <Tooltip title={fn} placement="topLeft">
            <span
              style={{
                fontSize: 13,
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                maxWidth: "100%",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {isHtml ? (
                <FileTextOutlined
                  style={{ marginRight: 6, color: "#fa8c16", flexShrink: 0 }}
                />
              ) : (
                <FileImageOutlined
                  style={{ marginRight: 6, color: "#1677ff", flexShrink: 0 }}
                />
              )}
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {fn}
              </span>
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: "所属群聊",
      key: "group",
      width: 180,
      ellipsis: true,
      render: (_: unknown, r: ReportItem) => {
        if (!r.group_id) {
          return <Text type="secondary">-</Text>;
        }
        const p =
          !r.platform || r.platform === "auto" || r.platform === "default"
            ? ""
            : r.platform;
        const label = `${r.group_name || "未知群"} (${r.group_id})`;
        return (
          <Tooltip
            title={`群号: ${r.group_id}${p ? ` | 平台: ${p}` : ""}${r.group_name ? ` | 群名: ${r.group_name}` : ""}`}
            placement="topLeft"
          >
            <span
              style={{
                fontSize: 12,
                display: "inline-flex",
                alignItems: "center",
                maxWidth: "100%",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              <TeamOutlined
                style={{ marginRight: 4, color: "#722ed1", flexShrink: 0 }}
              />
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {label}
              </span>
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: "平台",
      dataIndex: "platform",
      key: "platform",
      width: 75,
      align: "center" as const,
      render: (p?: string) => {
        const displayP = !p || p === "auto" || p === "default" ? "-" : p;
        return <Tag style={{ margin: 0 }}>{displayP}</Tag>;
      },
    },
    {
      title: "关联任务",
      dataIndex: "trace_id",
      key: "trace_id",
      width: 130,
      align: "center" as const,
      ellipsis: true,
      render: (tId?: string) => {
        if (!tId) return <Text type="secondary">-</Text>;
        return (
          <Tooltip title="点击在右侧抽屉查看任务详情与链路明细">
            <Tag
              color="blue"
              style={{
                cursor: "pointer",
                fontFamily:
                  'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                fontSize: 11,
                margin: 0,
                maxWidth: "100%",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              onClick={() => onViewTrace?.(tId)}
            >
              {tId}
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: "生成时间",
      dataIndex: "modified_at",
      key: "modified_at",
      width: 150,
      render: (ts: number) => (
        <span style={{ fontSize: 12, whiteSpace: "nowrap" }}>
          {formatTimestamp(ts)}
        </span>
      ),
    },
    {
      title: "文件大小",
      dataIndex: "size_bytes",
      key: "size_bytes",
      width: 90,
      align: "right" as const,
      render: (sz: number) => (
        <span style={{ fontSize: 12, whiteSpace: "nowrap" }}>
          {(sz / 1024).toFixed(1)} KB
        </span>
      ),
    },
    {
      title: <span style={{ whiteSpace: "nowrap" }}>服务器/容器存储路径</span>,
      dataIndex: "absolute_path",
      key: "absolute_path",
      width: 220,
      ellipsis: true,
      render: (path: string) =>
        path ? (
          <Paragraph
            copyable={{ text: path, tooltips: ["点击复制完整路径", "已复制"] }}
            ellipsis={{ rows: 1 }}
            style={{
              marginBottom: 0,
              fontSize: 12,
              maxWidth: "100%",
              fontFamily:
                'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
              whiteSpace: "nowrap",
            }}
          >
            {path}
          </Paragraph>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: "状态",
      key: "status",
      width: 75,
      align: "center" as const,
      render: () => (
        <Tag color="success" style={{ margin: 0 }}>
          已生成
        </Tag>
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 160,
      fixed: "right" as const,
      render: (_: unknown, r: ReportItem) => {
        const isHtml = Boolean(
          r.is_html ||
            r.filename.toLowerCase().endsWith(".html") ||
            r.filename.toLowerCase().endsWith(".htm")
        );
        return (
          <Space size="small" style={{ whiteSpace: "nowrap" }}>
            <Button
              size="small"
              type="primary"
              ghost
              icon={<EyeOutlined />}
              onClick={() => openPreview(r)}
            >
              {isHtml ? "预览 HTML" : "预览大图"}
            </Button>
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => downloadReport(r)}
            >
              下载
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <Card size="small" style={{ minHeight: 520 }}>
      {/* 历史报告筛选工具栏 (Feature) */}
      <ReportFilterBar
        search={search}
        selectedGroup={selectedGroup}
        groups={groups}
        loading={loading}
        onSearchChange={setSearch}
        onGroupChange={setSelectedGroup}
        onDateRangeChange={setDateRange}
        onRefresh={refresh}
      />

      {loading && rawReports.length === 0 ? (
        <div style={{ padding: "24px 12px" }}>
          <Skeleton
            active
            paragraph={{
              rows: 7,
              width: ["100%", "92%", "96%", "88%", "100%", "94%", "75%"],
            }}
          />
        </div>
      ) : rawReports.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无符合条件的历史图片报告产物"
          style={{ margin: "64px 0" }}
        />
      ) : (
        <Table
          size="small"
          columns={columns}
          dataSource={reports}
          rowKey="filename"
          loading={loading}
          scroll={{ x: 1200 }}
          pagination={{ pageSize: 10 }}
        />
      )}

      {/* 独立抽离的图片预览 Widget */}
      <ReportPreviewModal
        open={previewOpen}
        loading={previewLoading}
        report={selectedReport}
        onClose={closePreview}
        onDownload={downloadReport}
      />
    </Card>
  );
};

