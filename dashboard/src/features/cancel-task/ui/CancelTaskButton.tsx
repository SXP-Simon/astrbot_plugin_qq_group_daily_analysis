import React from "react";
import { Button, Popconfirm } from "antd";
import { StopOutlined } from "@ant-design/icons";

interface CancelTaskButtonProps {
  taskId: string;
  onCancel: (taskId: string) => Promise<void> | void;
}

export const CancelTaskButton: React.FC<CancelTaskButtonProps> = ({
  taskId,
  onCancel,
}) => {
  return (
    <Popconfirm
      title="确定要中止此分析任务吗？"
      description="中止后该群本次分析将立即停止并释放资源。"
      onConfirm={() => onCancel(taskId)}
      okText="确定中止"
      cancelText="取消"
      okButtonProps={{ danger: true, size: "small" }}
      cancelButtonProps={{ size: "small" }}
    >
      <Button
        danger
        size="small"
        type="link"
        icon={<StopOutlined />}
      >
        中止
      </Button>
    </Popconfirm>
  );
};
