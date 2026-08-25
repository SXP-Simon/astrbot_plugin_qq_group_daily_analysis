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
        <Form.Item label="群号 / 会话唯一标识 (Group ID)" required>
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

        <Form.Item label="平台类型 (Platform)">
          <Select
            value={platform}
            onChange={onPlatformChange}
            options={[
              { label: "QQ (OneBot / NapCat / Lagrange)", value: "qq" },
              { label: "Telegram", value: "telegram" },
              { label: "QQ 官方机器人 (QQ Official)", value: "qq_official" },
              { label: "飞书 (Lark)", value: "lark" },
              { label: "Discord", value: "discord" },
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};
