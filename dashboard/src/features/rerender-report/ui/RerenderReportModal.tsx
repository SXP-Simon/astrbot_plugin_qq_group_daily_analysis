import React, { useEffect, useState } from "react";
import { Modal, Form, Select, Radio, Alert, Space, Typography, message } from "antd";
import { SkinOutlined } from "@ant-design/icons";
import { ReportItem } from "../../../entities/report/model/types";
import { fetchReportTemplates, rerenderReport } from "../../../entities/report/api/reportApi";
import { formatTemplateOptions, ReportTemplateItem, DEFAULT_REPORT_TEMPLATES } from "../../../entities/report/model/templates";

const { Text } = Typography;

interface RerenderReportModalProps {
  open: boolean;
  report: ReportItem | null;
  onClose: () => void;
  onSuccess: () => void;
}

export const RerenderReportModal: React.FC<RerenderReportModalProps> = ({
  open,
  report,
  onClose,
  onSuccess,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState<ReportTemplateItem[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  useEffect(() => {
    if (open) {
      setLoadingTemplates(true);
      fetchReportTemplates()
        .then((list) => setTemplates(list))
        .catch(() => {
          message.warning("模板列表获取失败，已回退显示内置模板");
          setTemplates(DEFAULT_REPORT_TEMPLATES);
        })
        .finally(() => setLoadingTemplates(false));
    }
    if (open && report) {
      form.setFieldsValue({
        template_name: "scrapbook",
        render_format: report.is_html ? "html" : "image",
      });
    }
  }, [open, report, form]);

  const handleSubmit = async () => {
    if (!report) return;
    try {
      const values = await form.validateFields();
      setLoading(true);
      const res = await rerenderReport({
        group_id: report.group_id || "",
        template_name: values.template_name,
        render_format: values.render_format,
        platform_id: report.platform,
        trace_id: report.trace_id,
      });
      if (res && res.success) {
        message.success("✨ 免 Token 切换主题渲染成功！新报告已生成");
        onSuccess();
        onClose();
      } else {
        message.error("重新渲染失败，可能未找到该群的分析快照");
      }
    } catch {
      // Form validation or network error
    } finally {
      setLoading(false);
    }
  };

  const templateOptions = formatTemplateOptions(templates, false);

  return (
    <Modal
      title={
        <Space>
          <SkinOutlined style={{ color: "#722ed1" }} />
          <span>免 Token 切换主题模板重新渲染</span>
        </Space>
      }
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      confirmLoading={loading}
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
          <Text strong>{report?.group_name || report?.group_id || "-"}</Text>
        </Form.Item>
        <Form.Item
          name="template_name"
          label="视觉主题模板"
          rules={[{ required: true, message: "请选择视觉主题模板" }]}
        >
          <Select
            loading={loadingTemplates}
            options={templateOptions}
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
  );
};
