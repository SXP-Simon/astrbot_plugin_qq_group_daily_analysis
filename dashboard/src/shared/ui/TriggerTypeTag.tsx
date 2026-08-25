import React from "react";
import { Tag } from "antd";
import { formatTriggerType } from "../lib/formatters";

interface TriggerTypeTagProps {
  triggerType?: string;
  style?: React.CSSProperties;
}

export const TriggerTypeTag: React.FC<TriggerTypeTagProps> = ({ triggerType, style }) => {
  const { text, color } = formatTriggerType(triggerType);
  return (
    <Tag color={color} style={{ margin: 0, ...style }}>
      {text}
    </Tag>
  );
};
