import React, { useEffect, useState } from "react";
import { Modal, Alert, Form, Select, Space } from "antd";
import { SyncOutlined, ApiOutlined, SkinOutlined } from "@ant-design/icons";
import { fetchProviderList, LLMProviderItem } from "../../../entities/trace/api/traceApi";

interface ResumeTaskModalProps {
  open: boolean;
  loading: boolean;
  onCancel: () => void;
  onConfirm: (selectedProvider?: string, selectedTemplate?: string) => void;
}

export const ResumeTaskModal: React.FC<ResumeTaskModalProps> = ({
  open,
  loading,
  onCancel,
  onConfirm,
}) => {
  const [providers, setProviders] = useState<LLMProviderItem[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("auto");
  const [selectedTemplate, setSelectedTemplate] = useState("auto");

  useEffect(() => {
    if (open) {
      setSelectedProvider("auto");
      setSelectedTemplate("auto");
      setLoadingProviders(true);
      fetchProviderList()
        .then((list) => setProviders(list))
        .catch(() => {})
        .finally(() => setLoadingProviders(false));
    }
  }, [open]);

  const handleOk = () => {
    onConfirm(
      selectedProvider !== "auto" ? selectedProvider : undefined,
      selectedTemplate !== "auto" ? selectedTemplate : undefined
    );
  };

  return (
    <Modal
      title={
        <Space>
          <SyncOutlined />
          <span>幂等断点续跑 / 重试分析</span>
        </Space>
      }
      open={open}
      onCancel={onCancel}
      onOk={handleOk}
      confirmLoading={loading}
      okText="立即续跑"
      cancelText="取消"
      destroyOnClose
      width={460}
    >
      <div style={{ marginTop: 12 }}>
        <Alert
          type="info"
          showIcon
          message="零浪费 Token 细粒度产物复用"
          description="系统已自动跳过消息拉取与清洗，并直接复用本次任务中已有非空产物的子分析（如已生成的话题/画像），仅对失败或未完成的子任务向大模型发起补充请求。"
          style={{ marginBottom: 16 }}
        />

        <Form layout="vertical">
          <Form.Item
            label={
              <Space>
                <ApiOutlined />
                <span>指定大模型 Provider (选填)</span>
              </Space>
            }
            extra="若上次分析因大模型崩溃、限流或 Provider 故障中断，可在此临时指定其他备用模型完成续跑"
          >
            <Select
              value={selectedProvider}
              onChange={setSelectedProvider}
              loading={loadingProviders}
              options={[
                { label: "跟随系统默认配置 (推荐)", value: "auto" },
                ...providers.map((p) => ({
                  label: p.label || `${p.name} (${p.id})`,
                  value: p.id,
                })),
              ]}
            />
          </Form.Item>

          <Form.Item
            label={
              <Space>
                <SkinOutlined style={{ color: "#722ed1" }} />
                <span>视觉主题模板 (选填)</span>
              </Space>
            }
            extra="续跑生成报告时可切换报告排版视觉模板"
          >
            <Select
              value={selectedTemplate}
              onChange={setSelectedTemplate}
              options={[
                { label: "跟随系统默认配置 (推荐)", value: "auto" },
                { label: "手账风格 (Scrapbook)", value: "scrapbook" },
                { label: "亚托莉 (ATRI)", value: "ATRI" },
                { label: "初音未来 (HatsuneMiku)", value: "HatsuneMiku" },
                { label: "复古未来 (Retro Futurism)", value: "retro_futurism" },
                { label: "黑客赛博 (Hack)", value: "hack" },
                { label: "蔚蓝档案 (BlueArchive)", value: "BlueArchive" },
                { label: "极简黑白 (Simple)", value: "simple" },
              ]}
            />
          </Form.Item>
        </Form>
      </div>
    </Modal>
  );
};
