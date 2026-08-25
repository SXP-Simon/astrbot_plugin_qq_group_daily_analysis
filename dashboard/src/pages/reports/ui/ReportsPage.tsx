import React, { useState } from "react";
import {
  Card,
  Table,
  Empty,
  Button,
  Tag,
  Modal,
  Typography,
  Space,
  Spin,
  message,
} from "antd";
import {
  ReloadOutlined,
  FileImageOutlined,
  FolderOpenOutlined,
  EyeOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import { formatTimestamp } from "../../../shared/lib/formatters";
import { useReportsViewModel } from "../model/useReportsViewModel";
import { fetchReportContent } from "../../../entities/report/api/reportApi";
import { ReportItem } from "../../../entities/report/model/types";

const { Text, Paragraph } = Typography;

interface ReportsPageProps {
  viewModel: ReturnType<typeof useReportsViewModel>;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({ viewModel }) => {
  const { reports, loading, refresh } = viewModel;

  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [currentReport, setCurrentReport] = useState<ReportItem | null>(null);

  const handleOpenPreview = async (report: ReportItem) => {
    setCurrentReport(report);
    setPreviewOpen(true);
    setPreviewLoading(true);
    try {
      const data = await fetchReportContent(report.filename);
      if (data && data.data_url) {
        setCurrentReport((prev) => ({
          ...(prev || report),
          ...data,
        }));
      } else {
        message.warning("未能读取到报告图片数据");
      }
    } catch {
      message.error("加载报告图片失败");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDirectDownload = async (report: ReportItem) => {
    try {
      let dataUrl = report.data_url;
      if (!dataUrl) {
        const data = await fetchReportContent(report.filename);
        dataUrl = data?.data_url;
      }
      if (!dataUrl) {
        message.error("获取下载图片失败");
        return;
      }

      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = report.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      message.success(`已开始下载 ${report.filename}`);
    } catch {
      message.error("下载文件异常");
    }
  };

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
            onClick={() => handleOpenPreview(r)}
          >
            预览大图
          </Button>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => handleDirectDownload(r)}
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

      {/* 图片预览 Modal */}
      <Modal
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        title={
          <Space>
            <FileImageOutlined style={{ color: "#1677ff" }} />
            <span style={{ fontSize: 15, fontWeight: 600 }}>
              {currentReport?.filename || "日报长图预览"}
            </span>
          </Space>
        }
        width={720}
        footer={[
          <Button key="close" onClick={() => setPreviewOpen(false)}>
            关闭
          </Button>,
          currentReport && (
            <Button
              key="download"
              type="primary"
              icon={<DownloadOutlined />}
              onClick={() => handleDirectDownload(currentReport)}
            >
              下载图片
            </Button>
          ),
        ]}
        destroyOnHidden
      >
        {previewLoading ? (
          <div style={{ textAlign: "center", padding: "60px 0" }}>
            <Spin tip="正在加载高清报告图片..." />
          </div>
        ) : currentReport?.data_url ? (
          <div style={{ textAlign: "center" }}>
            {currentReport.absolute_path && (
              <div
                style={{
                  marginBottom: 12,
                  padding: "6px 12px",
                  background: "rgba(0,0,0,0.03)",
                  borderRadius: 4,
                  textAlign: "left",
                  fontSize: 12,
                }}
              >
                <Text type="secondary">文件路径：</Text>
                <Text copyable style={{ fontSize: 12 }}>
                  {currentReport.absolute_path}
                </Text>
              </div>
            )}
            <div
              style={{
                maxHeight: "65vh",
                overflowY: "auto",
                border: "1px solid #f0f0f0",
                borderRadius: 4,
                padding: 8,
                background: "#fafafa",
              }}
            >
              <img
                src={currentReport.data_url}
                alt={currentReport.filename}
                style={{
                  maxWidth: "100%",
                  height: "auto",
                  display: "block",
                  margin: "0 auto",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                }}
              />
            </div>
          </div>
        ) : (
          <Empty description="未找到图片数据" />
        )}
      </Modal>
    </>
  );
};

