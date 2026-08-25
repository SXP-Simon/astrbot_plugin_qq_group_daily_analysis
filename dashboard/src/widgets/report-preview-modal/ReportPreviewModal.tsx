import React from "react";
import { Modal, Button, Space, Typography, Spin, Empty } from "antd";
import {
  FileImageOutlined,
  DownloadOutlined,
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
  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={
        <Space>
          <FileImageOutlined style={{ color: "#1677ff" }} />
          <span style={{ fontSize: 15, fontWeight: 600 }}>
            {report?.filename || "日报长图预览"}
          </span>
        </Space>
      }
      width={720}
      footer={[
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
        report && (
          <Button
            key="download"
            type="primary"
            icon={<DownloadOutlined />}
            onClick={() => onDownload(report)}
          >
            下载图片
          </Button>
        ),
      ]}
      destroyOnHidden
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <Spin tip="正在加载高清报告图片..." />
        </div>
      ) : report?.data_url ? (
        <div style={{ textAlign: "center" }}>
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
              <Text type="secondary">文件路径：</Text>
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
        </div>
      ) : (
        <Empty description="未找到图片数据" style={{ margin: "40px 0" }} />
      )}
    </Modal>
  );
};
