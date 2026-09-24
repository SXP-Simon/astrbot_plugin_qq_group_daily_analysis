import React from "react";
import {
  Modal,
  Button,
  Space,
  Descriptions,
  Tag,
  Typography,
  message,
  theme,
} from "antd";
import {
  SaveOutlined,
  CopyOutlined,
} from "@ant-design/icons";
import { CheckpointDetail } from "../../../../entities/plugin-data/model/types";
import { formatBytes, formatStageName } from "../../../../shared/lib/formatters";
import { SANS_NUM_STYLE, getStageMeta, handleCopyJson } from "../constants";

const { Text } = Typography;

interface CheckpointDetailModalProps {
  open: boolean;
  onClose: () => void;
  ckptDetail: CheckpointDetail | null;
  loading: boolean;
}

export const CheckpointDetailModal: React.FC<CheckpointDetailModalProps> = ({
  open,
  onClose,
  ckptDetail,
  loading,
}) => {
  const { token } = theme.useToken();

  return (
    <Modal
      title={
        <Space>
          <SaveOutlined style={{ color: "#2563eb" }} />
          <span>
            阶段快照产物 JSON:{" "}
            {formatStageName(ckptDetail?.stage_name)} (
            {ckptDetail?.stage_name || "-"})
          </span>
        </Space>
      }
      open={open}
      onCancel={onClose}
      footer={[
        <Button
          key="copy"
          icon={<CopyOutlined />}
          onClick={() => handleCopyJson(ckptDetail?.data)}
        >
          复制产物数据
        </Button>,
        <Button key="close" type="primary" onClick={onClose}>
          关闭
        </Button>,
      ]}
      width={850}
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: "30px 0" }}>
          <Text type="secondary">加载快照产物数据中...</Text>
        </div>
      ) : ckptDetail ? (
        <Space direction="vertical" size="small" style={{ width: "100%" }}>
          <Descriptions
            size="small"
            bordered
            column={{ xs: 1, sm: 2, md: 2 }}
            style={{ marginBottom: 4 }}
            items={[
              {
                key: "group",
                label: "群聊号码",
                children: (
                  <Text strong style={SANS_NUM_STYLE}>
                    {ckptDetail.group_id || "-"}
                  </Text>
                ),
              },
              {
                key: "date",
                label: "分析归属日期",
                children: (
                  <Tag color="cyan" style={SANS_NUM_STYLE}>
                    {ckptDetail.date_str || "-"}
                  </Tag>
                ),
              },
              {
                key: "stage",
                label: "流水线阶段",
                children: (
                  <Tag
                    color={getStageMeta(ckptDetail.stage_name || "").color}
                    style={{ fontSize: 12, margin: 0 }}
                  >
                    {formatStageName(ckptDetail.stage_name)} (
                    {ckptDetail.stage_name || "-"})
                  </Tag>
                ),
              },
              {
                key: "size",
                label: "快照产物大小",
                children: (
                  <span style={SANS_NUM_STYLE}>
                    {formatBytes(
                      ckptDetail.data_size_bytes ??
                        ckptDetail.data_size ??
                        0
                    )}
                  </span>
                ),
              },
              {
                key: "trace_id",
                label: "任务 Trace ID",
                span: 2,
                children: ckptDetail.trace_id ? (
                  <Space size={8} wrap align="center">
                    <Tag
                      color="geekblue"
                      style={{ fontSize: 12, margin: 0, ...SANS_NUM_STYLE }}
                    >
                      {ckptDetail.trace_id}
                    </Tag>
                    <Button
                      size="small"
                      type="dashed"
                      icon={<CopyOutlined />}
                      onClick={() => {
                        navigator.clipboard.writeText(
                          ckptDetail.trace_id || ""
                        );
                        message.success("已复制 Trace ID 到剪贴板");
                      }}
                      style={{ fontSize: 11, height: 22, padding: "0 6px" }}
                    >
                      复制
                    </Button>
                  </Space>
                ) : (
                  <Tag color="default">Legacy (按天快照，未关联 Trace ID)</Tag>
                ),
              },
            ]}
          />

          <div>
            <Text
              strong
              style={{ fontSize: 12, marginBottom: 4, display: "block" }}
            >
              阶段产物数据 (JSON):
            </Text>
            <pre
              style={{
                fontSize: 11,
                fontFamily:
                  "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, monospace",
                background: token.colorFillAlter,
                color: token.colorText,
                border: `1px solid ${token.colorBorderSecondary}`,
                padding: "8px 10px",
                borderRadius: 4,
                maxHeight: 340,
                overflowY: "auto",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                margin: 0,
              }}
            >
              {JSON.stringify(ckptDetail.data, null, 2)}
            </pre>
          </div>
        </Space>
      ) : null}
    </Modal>
  );
};
