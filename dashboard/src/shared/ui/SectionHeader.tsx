import React from "react";
import { Space, Typography } from "antd";

const { Text } = Typography;

interface SectionHeaderProps {
  icon?: React.ReactNode;
  title: string;
  badge?: React.ReactNode;
  extra?: React.ReactNode;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  icon,
  title,
  badge,
  extra,
}) => {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 10,
      }}
    >
      <Space size="small" align="center">
        {icon}
        <Text strong style={{ fontSize: 13 }}>
          {title}
        </Text>
        {badge}
      </Space>
      {extra && <div>{extra}</div>}
    </div>
  );
};
