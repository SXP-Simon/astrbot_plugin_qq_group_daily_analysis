import React from "react";
import { Modal, Form, Input, Select } from "antd";
import { ConnectedPlatform } from "../../../entities/task/api/taskApi";

interface TriggerTaskModalProps {
  open: boolean;
  groupId: string;
  groupName: string;
  platform: string;
  submitting: boolean;
  connectedPlatforms?: ConnectedPlatform[];
  loadingPlatforms?: boolean;
  onGroupIdChange: (val: string) => void;
  onGroupNameChange: (val: string) => void;
  onPlatformChange: (val: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}

export const TriggerTaskModal: React.FC<TriggerTaskModalProps> = ({
  open,
  groupId,
  groupName,
  platform,
  submitting,
  connectedPlatforms = [],
  loadingPlatforms = false,
  onGroupIdChange,
  onGroupNameChange,
  onPlatformChange,
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
      width={440}
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
      </Form>
    </Modal>
  );
};
