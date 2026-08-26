import React, { useState } from "react";
import {
  Card,
  Table,
  Empty,
  Button,
  Tag,
  Typography,
  Space,
  Tooltip,
  Skeleton,
} from "antd";
import {
  FileImageOutlined,
  FileTextOutlined,
  PictureOutlined,
  EyeOutlined,
  DownloadOutlined,
  SkinOutlined,
} from "@ant-design/icons";
import { formatTimestamp } from "../../../shared/lib/formatters";
import { useReportsViewModel } from "../model/useReportsViewModel";
import { ReportItem } from "../../../entities/report/model/types";
import { ReportPreviewModal } from "../../../widgets/report-preview-modal/ReportPreviewModal";
import { ReportFilterBar } from "../../../features/filter-reports/ui/ReportFilterBar";
import { RerenderReportModal } from "../../../features/rerender-report/ui/RerenderReportModal";

const { Text } = Typography;

interface ReportsPageProps {
  viewModel: ReturnType<typeof useReportsViewModel>;
  onViewTrace?: (traceId: string) => void;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({ viewModel, onViewTrace }) => {
  const [rerenderModalOpen, setRerenderModalOpen] = useState(false);
  const [rerenderingReport, setRerenderingReport] = useState<ReportItem | null>(null);

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
        const isComic = Boolean(
          r.is_comic ||
            fn.toLowerCase().startsWith("comic_") ||
            fn.startsWith("漫画_")
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
              {isComic ? (
                <PictureOutlined
                  style={{ marginRight: 6, color: "#eb2f96", flexShrink: 0 }}
                />
              ) : isHtml ? (
                <FileTextOutlined
                  style={{ marginRight: 6, color: "#fa8c16", flexShrink: 0 }}
                />
              ) : (
                <FileImageOutlined
                  style={{ marginRight: 6, color: "#1677ff", flexShrink: 0 }}
                />
              )}
              {fn}
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: "类型",
      dataIndex: "is_comic",
      key: "type",
      width: 100,
      render: (_: boolean, r: ReportItem) => {
        const isHtml = Boolean(
          r.is_html ||
            r.filename.toLowerCase().endsWith(".html") ||
            r.filename.toLowerCase().endsWith(".htm")
        );
        const isComic = Boolean(
          r.is_comic ||
            r.filename.toLowerCase().startsWith("comic_") ||
            r.filename.startsWith("漫画_")
        );
        if (isComic) {
          return <Tag color="magenta">群漫画</Tag>;
        }
        return isHtml ? (
          <Tag color="orange">交互式 HTML</Tag>
        ) : (
          <Tag color="blue">长图海报</Tag>
        );
      },
    },
    {
      title: "目标群聊",
      dataIndex: "group_id",
      key: "group",
      width: 170,
      render: (gid: string, r: ReportItem) => (
        <span style={{ fontSize: 12 }}>
          {r.group_name ? (
            <span>
              {r.group_name} <Text type="secondary">({gid || "-"})</Text>
            </span>
          ) : (
            gid || "-"
          )}
        </span>
      ),
    },
    {
      title: "接入平台",
      dataIndex: "platform",
      key: "platform",
      width: 110,
      render: (platform: string) => (
        <Tag style={{ margin: 0 }}>
          {!platform || platform === "auto" || platform === "default"
            ? "-"
            : platform}
        </Tag>
      ),
    },
    {
      title: "关联分析任务",
      dataIndex: "trace_id",
      key: "trace_id",
      width: 150,
      render: (tid: string) => {
        if (!tid) {
          return (
            <Text type="secondary" style={{ fontSize: 11 }}>
              历史遗留
            </Text>
          );
        }
        return (
          <Tooltip title="点击在右侧查看该报告完整的全阶段分析指标与时间线">
            <Button
              type="link"
              size="small"
              onClick={() => onViewTrace && onViewTrace(tid)}
              style={{
                padding: 0,
                fontSize: 11,
                fontFamily:
                  'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                height: "auto",
              }}
            >
              {tid}
            </Button>
          </Tooltip>
        );
      },
    },
    {
      title: "文件大小",
      dataIndex: "size_bytes",
      key: "size_bytes",
      width: 90,
      render: (bytes: number) => (
        <span style={{ fontSize: 12 }}>
          {bytes > 0 ? `${(bytes / 1024).toFixed(1)} KB` : "-"}
        </span>
      ),
    },
    {
      title: "生成时间",
      dataIndex: "modified_at",
      key: "modified_at",
      width: 160,
      render: (ts: number) => (
        <span style={{ fontSize: 12 }}>{formatTimestamp(ts)}</span>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 220,
      fixed: "right" as const,
      render: (_: unknown, r: ReportItem) => {
        const isComic = Boolean(
          r.is_comic ||
            r.filename.toLowerCase().startsWith("comic_") ||
            r.filename.startsWith("漫画_")
        );
        return (
          <Space size="small">
            <Button
              type="primary"
              size="small"
              ghost
              icon={<EyeOutlined />}
              onClick={() => openPreview(r)}
            >
              预览
            </Button>
            {!isComic && (
              <Button
                size="small"
                icon={<SkinOutlined />}
                onClick={() => {
                  setRerenderingReport(r);
                  setRerenderModalOpen(true);
                }}
                style={{ color: "#722ed1", borderColor: "#d3adf7" }}
              >
                换模板
              </Button>
            )}
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

      {/* 免 Token 换主题重新生成报告 Modal (Feature) */}
      <RerenderReportModal
        open={rerenderModalOpen}
        report={rerenderingReport}
        onClose={() => {
          setRerenderModalOpen(false);
          setRerenderingReport(null);
        }}
        onSuccess={refresh}
      />
    </Card>
  );
};
