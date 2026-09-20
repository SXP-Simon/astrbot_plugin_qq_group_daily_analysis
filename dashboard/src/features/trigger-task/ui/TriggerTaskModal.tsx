import React from "react";
import { Modal, Form, Input, Select } from "antd";
import { ConnectedPlatform } from "../../../entities/task/api/taskApi";
import { LLMProviderItem } from "../../../entities/trace/api/traceApi";
import { ReportTemplateItem, formatTemplateOptions } from "../../../entities/report/model/templates";

interface TriggerTaskModalProps {
  open: boolean;
  groupId: string;
  groupName: string;
  platform: string;
  providerId?: string;
  templateName?: string;
  submitting: boolean;
  connectedPlatforms?: ConnectedPlatform[];
  loadingPlatforms?: boolean;
  providers?: LLMProviderItem[];
  loadingProviders?: boolean;
  templates?: ReportTemplateItem[];
  loadingTemplates?: boolean;
  onGroupIdChange: (val: string) => void;
  onGroupNameChange: (val: string) => void;
  onPlatformChange: (val: string) => void;
  onProviderChange?: (val: string) => void;
  onTemplateChange?: (val: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}

export const TriggerTaskModal: React.FC<TriggerTaskModalProps> = ({
  open,
  groupId,
  groupName,
  platform,
  providerId = "auto",
  templateName = "auto",
  submitting,
  connectedPlatforms = [],
  loadingPlatforms = false,
  providers = [],
  loadingProviders = false,
  templates = [],
  loadingTemplates = false,
  onGroupIdChange,
  onGroupNameChange,
  onPlatformChange,
  onProviderChange,
  onTemplateChange,
  onClose,
  onSubmit,
}) => {
  const platformOptions = [
    { label: "自动识别 / 默认平台 (推荐)", value: "auto" },
    ...(connectedPlatforms.length > 0
      ? connectedPlatforms.map((p) => ({
          label: p.label,
          value: p.id,
        }))
      : [
          { label: "OneBot (aiocqhttp)", value: "aiocqhttp" },
          { label: "QQ 官方机器人", value: "qq_official" },
          { label: "Telegram", value: "telegram" },
          { label: "Discord", value: "discord" },
        ]),
  ];

  const providerOptions = [
    { label: "跟随系统默认配置 (推荐)", value: "auto" },
    ...providers.map((p) => ({
      label: p.label || `${p.name} (${p.id})`,
      value: p.id,
    })),
  ];

  const templateOptions = formatTemplateOptions(templates, true);

  return (
    <Modal
      title="手动触发群聊日报分析"
      open={open}
      onOk={onSubmit}
      onCancel={onClose}
      confirmLoading={submitting}
      okText="立即触发"
      cancelText="取消"
      destroyOnClose
      width={460}
    >
      <Form layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item label="群号 / 会话标识" required>
          <Input
            placeholder="例如: 123456789"
            value={groupId}
            onChange={(e) => onGroupIdChange(e.target.value)}
            autoFocus
          />
        </Form.Item>

        <Form.Item label="群名称 (选填)">
          <Input
            placeholder="例如: 核心交流群"
            value={groupName}
            onChange={(e) => onGroupNameChange(e.target.value)}
          />
        </Form.Item>

        <Form.Item
          label="接入平台"
          extra={
            connectedPlatforms.length > 0
              ? `已自动检测到 ${connectedPlatforms.length} 个活跃平台实例，支持自由指定`
              : "自动调用当前已连接的 Bot 平台进行消息抓取与报告发送"
          }
        >
          <Select
            value={platform}
            onChange={onPlatformChange}
            loading={loadingPlatforms}
            options={platformOptions}
          />
        </Form.Item>

        <Form.Item
          label="指定大模型 Provider (选填)"
          extra="若希望本次分析使用特定 Provider 处理大模型语义分析，可在此选择"
        >
          <Select
            value={providerId}
            onChange={onProviderChange}
            loading={loadingProviders}
            options={providerOptions}
          />
        </Form.Item>

        <Form.Item
          label="报告视觉模板 (选填)"
          extra="指定本次分析生成的报告模板主题，留空则使用基础配置中的默认模板"
        >
          <Select
            value={templateName}
            onChange={onTemplateChange}
            loading={loadingTemplates}
            options={templateOptions}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};

