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
  Modal,
  Form,
  Select,
  Radio,
  Alert,
  message,
} from "antd";
import {
  FileImageOutlined,
  FileTextOutlined,
  PictureOutlined,
  EyeOutlined,
  DownloadOutlined,
  TeamOutlined,
  SkinOutlined,
} from "@ant-design/icons";
import { formatTimestamp } from "../../../shared/lib/formatters";
import { useReportsViewModel } from "../model/useReportsViewModel";
import { ReportItem } from "../../../entities/report/model/types";
import { rerenderReport } from "../../../entities/report/api/reportApi";
import { ReportPreviewModal } from "../../../widgets/report-preview-modal/ReportPreviewModal";
import { ReportFilterBar } from "../../../features/filter-reports/ui/ReportFilterBar";

const { Text, Paragraph } = Typography;

interface ReportsPageProps {
  viewModel: ReturnType<typeof useReportsViewModel>;
  onViewTrace?: (traceId: string) => void;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({ viewModel, onViewTrace }) => {
  const [rerenderModalOpen, setRerenderModalOpen] = useState(false);
  const [rerenderingReport, setRerenderingReport] = useState<ReportItem | null>(null);
  const [rerenderLoading, setRerenderLoading] = useState(false);
  const [form] = Form.useForm();
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
              <Tag
                color={isComic ? "magenta" : isHtml ? "orange" : "blue"}
                style={{ margin: "0 6px 0 0", fontSize: 10, lineHeight: "16px", flexShrink: 0 }}
              >
                {isComic ? "群漫画" : isHtml ? "HTML" : "日报长图"}
              </Tag>
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
      width: 240,
      fixed: "right" as const,
      render: (_: unknown, r: ReportItem) => {
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
        return (
          <Space size="small" style={{ whiteSpace: "nowrap" }}>
            <Button
              size="small"
              type="primary"
              ghost
              icon={<EyeOutlined />}
              onClick={() => openPreview(r)}
            >
              {isComic ? "预览漫画" : isHtml ? "预览 HTML" : "预览大图"}
            </Button>
            {!isComic && (
              <Button
                size="small"
                icon={<SkinOutlined />}
                onClick={() => {
                  setRerenderingReport(r);
                  form.setFieldsValue({
                    template_name: "scrapbook",
                    render_format: isHtml ? "html" : "image",
                  });
                  setRerenderModalOpen(true);
                }}
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

  const handleRerenderSubmit = async () => {
    if (!rerenderingReport) return;
    try {
      const values = await form.validateFields();
      setRerenderLoading(true);
      const res = await rerenderReport({
        group_id: rerenderingReport.group_id || "",
        template_name: values.template_name,
        render_format: values.render_format,
        platform_id: rerenderingReport.platform,
      });
      if (res && res.success) {
        message.success("✨ 免 Token 切换主题渲染成功！新报告已生成");
        setRerenderModalOpen(false);
        refresh();
      } else {
        message.error("重新渲染失败，可能未找到该群的分析快照");
      }
    } catch {
      // 表单校验或网络异常
    } finally {
      setRerenderLoading(false);
    }
  };

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

      {/* 免 Token 换主题重新生成报告 Modal */}
      <Modal
        title={
          <Space>
            <SkinOutlined style={{ color: "#722ed1" }} />
            <span>免 Token 切换主题模板重新渲染</span>
          </Space>
        }
        open={rerenderModalOpen}
        onCancel={() => setRerenderModalOpen(false)}
        onOk={handleRerenderSubmit}
        confirmLoading={rerenderLoading}
        okText="立即重新渲染"
        cancelText="取消"
        destroyOnClose
      >
        <Alert
          type="info"
          showIcon
          message="基于已有分析快照（Checkpoint）重绘"
          description="直接复用该群先前的聊天统计、话题总结与群友画像数据，无需再次调用大模型，消耗 0 Token。"
          style={{ marginBottom: 16 }}
        />
        <Form form={form} layout="vertical">
          <Form.Item label="目标群聊">
            <Text strong>{rerenderingReport?.group_name || rerenderingReport?.group_id || "-"}</Text>
          </Form.Item>
          <Form.Item
            name="template_name"
            label="视觉主题模板"
            rules={[{ required: true, message: "请选择视觉主题模板" }]}
          >
            <Select
              options={[
                { label: "手账风格 (Scrapbook / 默认)", value: "scrapbook" },
                { label: "亚托莉 (ATRI)", value: "ATRI" },
                { label: "初音未来 (HatsuneMiku)", value: "HatsuneMiku" },
                { label: "复古未来 (Retro Futurism)", value: "retro_futurism" },
                { label: "黑客赛博 (Hack)", value: "hack" },
                { label: "蔚蓝档案 (BlueArchive)", value: "BlueArchive" },
                { label: "极简黑白 (Simple)", value: "simple" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="render_format"
            label="输出格式"
            rules={[{ required: true, message: "请选择输出格式" }]}
          >
            <Radio.Group>
              <Radio value="image">长图海报 (.jpg)</Radio>
              <Radio value="html">交互式网页 (.html)</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

