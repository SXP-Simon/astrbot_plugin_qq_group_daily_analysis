import React from "react";
import { Tag } from "antd";
import { SyncOutlined } from "@ant-design/icons";

interface TaskStageBadgeProps {
  stage: string;
}

export const TaskStageBadge: React.FC<TaskStageBadgeProps> = ({ stage }) => {
  let color = "processing";
  let label = stage;

  if (stage.includes("FETCH")) {
    color = "blue";
    label = "拉取消息";
  } else if (stage.includes("LLM") || stage.includes("ANALYSIS")) {
    color = "purple";
    label = "大模型分析";
  } else if (stage.includes("RENDER") || stage.includes("REPORT")) {
    color = "orange";
    label = "渲染排版";
  } else if (stage.includes("DISPATCH") || stage.includes("SEND")) {
    color = "cyan";
    label = "下发推送";
  }

  return (
    <Tag icon={<SyncOutlined spin />} color={color} className="font-mono text-xs">
      {label}
    </Tag>
  );
};
