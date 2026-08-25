import React from "react";
import { Modal, Form, Input, Select } from "antd";

interface TriggerTaskModalProps {
  open: boolean;
  groupId: string;
  groupName: string;
  platform: string;
  submitting: boolean;
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
  onGroupIdChange,
  onGroupNameChange,
  onPlatformChange,
  onClose,
  onSubmit,
}) => {
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

        <Form.Item label="聊天平台">
          <Select
            value={platform}
            onChange={onPlatformChange}
            options={[
              { label: "QQ (OneBot 协议端)", value: "qq" },
              { label: "QQ 官方机器人", value: "qq_official" },
              { label: "Telegram", value: "telegram" },
              { label: "飞书", value: "lark" },
              { label: "Discord", value: "discord" },
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};
