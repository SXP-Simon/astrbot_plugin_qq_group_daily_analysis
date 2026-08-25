import React from "react";
import { Card, Table, Empty, Button, Tag, Typography, Space } from "antd";
import {
  ReloadOutlined,
  FileImageOutlined,
  FolderOpenOutlined,
  EyeOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import { formatTimestamp } from "../../../shared/lib/formatters";
import { useReportsViewModel } from "../model/useReportsViewModel";
import { ReportItem } from "../../../entities/report/model/types";
import { ReportPreviewModal } from "../../../widgets/report-preview-modal/ReportPreviewModal";

const { Text, Paragraph } = Typography;

interface ReportsPageProps {
  viewModel: ReturnType<typeof useReportsViewModel>;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({ viewModel }) => {
  const {
    reports,
    loading,
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
      width: 280,
      render: (fn: string) => (
        <span style={{ fontSize: 13, fontWeight: 600 }}>
          <FileImageOutlined style={{ marginRight: 6, color: "#1677ff" }} />
          {fn}
        </span>
      ),
    },
    {
      title: "本地存储路径",
      dataIndex: "absolute_path",
      key: "absolute_path",
      render: (path: string) =>
        path ? (
          <Paragraph
            copyable={{ text: path, tooltips: ["点击复制完整路径", "已复制"] }}
            ellipsis={{ rows: 1 }}
            style={{
              marginBottom: 0,
              fontSize: 12,
              color: "#595959",
              maxWidth: 380,
              fontFamily:
                'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
            }}
          >
            {path}
          </Paragraph>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: "文件大小",
      dataIndex: "size_bytes",
      key: "size_bytes",
      width: 110,
      render: (sz: number) => (
        <span style={{ fontSize: 12 }}>{(sz / 1024).toFixed(1)} KB</span>
      ),
    },
    {
      title: "生成时间",
      dataIndex: "modified_at",
      key: "modified_at",
      width: 170,
      render: (ts: number) => (
        <span style={{ color: "#595959", fontSize: 12 }}>
          {formatTimestamp(ts)}
        </span>
      ),
    },
    {
      title: "状态",
      key: "status",
      width: 85,
      render: () => <Tag color="success">已生成</Tag>,
    },
    {
      title: "操作",
      key: "actions",
      width: 170,
      render: (_: unknown, r: ReportItem) => (
        <Space size="small">
          <Button
            size="small"
            type="primary"
            ghost
            icon={<EyeOutlined />}
            onClick={() => openPreview(r)}
          >
            预览大图
          </Button>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => downloadReport(r)}
          >
            下载
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        size="small"
        title={
          <span>
            <FolderOpenOutlined style={{ marginRight: 6, color: "#1677ff" }} />
            历史生成的日报长图
          </span>
        }
        extra={
          <Button
            size="small"
            icon={<ReloadOutlined spin={loading} />}
            onClick={refresh}
          >
            刷新
          </Button>
        }
      >
        {reports.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无历史图片报告产物"
            style={{ margin: "32px 0" }}
          />
        ) : (
          <Table
            size="small"
            columns={columns}
            dataSource={reports}
            rowKey="filename"
            loading={loading}
            pagination={{ pageSize: 10 }}
          />
        )}
      </Card>

      {/* 独立抽离的图片预览 Widget */}
      <ReportPreviewModal
        open={previewOpen}
        loading={previewLoading}
        report={selectedReport}
        onClose={closePreview}
        onDownload={downloadReport}
      />
    </>
  );
};

