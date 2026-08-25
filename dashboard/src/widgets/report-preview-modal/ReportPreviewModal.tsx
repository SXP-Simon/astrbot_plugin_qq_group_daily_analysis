import React from "react";
import { Modal, Button, Space, Typography, Spin, Empty } from "antd";
import {
  FileImageOutlined,
  FileTextOutlined,
  DownloadOutlined,
  ExportOutlined,
} from "@ant-design/icons";
import { ReportItem } from "../../entities/report/model/types";

const { Text } = Typography;

interface ReportPreviewModalProps {
  open: boolean;
  loading: boolean;
  report: ReportItem | null;
  onClose: () => void;
  onDownload: (report: ReportItem) => void;
}

export const ReportPreviewModal: React.FC<ReportPreviewModalProps> = ({
  open,
  loading,
  report,
  onClose,
  onDownload,
}) => {
  const isHtml = Boolean(
    report?.is_html ||
      report?.filename.toLowerCase().endsWith(".html") ||
      report?.filename.toLowerCase().endsWith(".htm")
  );

  const handleOpenInNewTab = () => {
    if (!report) return;
    if (isHtml && report.html_content) {
      const blob = new Blob([report.html_content], { type: "text/html;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    } else if (report.data_url) {
      window.open(report.data_url, "_blank");
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={
        <Space>
          {isHtml ? (
            <FileTextOutlined style={{ color: "#fa8c16" }} />
          ) : (
            <FileImageOutlined style={{ color: "#1677ff" }} />
          )}
          <span style={{ fontSize: 15, fontWeight: 600 }}>
            {report?.filename || (isHtml ? "HTML 报告预览" : "日报长图预览")}
          </span>
        </Space>
      }
      width={isHtml ? 920 : 760}
      footer={[
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
        report && (
          <Button
            key="open-tab"
            icon={<ExportOutlined />}
            onClick={handleOpenInNewTab}
          >
            新窗口打开
          </Button>
        ),
        report && (
          <Button
            key="download"
            type="primary"
            icon={<DownloadOutlined />}
            onClick={() => onDownload(report)}
          >
            {isHtml ? "下载 HTML" : "下载图片"}
          </Button>
        ),
      ]}
      destroyOnHidden
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <Spin tip={isHtml ? "正在加载 HTML 报告内容..." : "正在加载高清报告图片..."} />
        </div>
      ) : report?.data_url || (isHtml && report?.html_content) ? (
        <div>
          {report.absolute_path && (
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
              <Text type="secondary">服务器/容器文件路径：</Text>
              <Text
                copyable
                style={{
                  fontSize: 12,
                  fontFamily:
                    'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                }}
              >
                {report.absolute_path}
              </Text>
            </div>
          )}
          {isHtml ? (
            <div
              style={{
                border: "1px solid #f0f0f0",
                borderRadius: 6,
                overflow: "hidden",
                background: "#ffffff",
              }}
            >
              <iframe
                title={report.filename}
                srcDoc={report.html_content || undefined}
                src={!report.html_content ? report.data_url : undefined}
                sandbox="allow-scripts allow-same-origin"
                style={{
                  width: "100%",
                  height: "68vh",
                  border: "none",
                  display: "block",
                }}
              />
            </div>
          ) : (
            <div
              style={{
                maxHeight: "68vh",
                overflowY: "auto",
                border: "1px solid #f0f0f0",
                borderRadius: 4,
                padding: 8,
                background: "#fafafa",
              }}
            >
              <img
                src={report.data_url}
                alt={report.filename}
                style={{
                  maxWidth: "100%",
                  height: "auto",
                  display: "block",
                  margin: "0 auto",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                }}
              />
            </div>
          )}
        </div>
      ) : (
        <Empty description="未找到报告文件内容" style={{ margin: "40px 0" }} />
      )}
    </Modal>
  );
};
