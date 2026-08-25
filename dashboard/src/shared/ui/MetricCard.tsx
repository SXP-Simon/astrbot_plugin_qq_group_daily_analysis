import React from "react";
import { Card, Statistic } from "antd";

interface MetricCardProps {
  title: string;
  value: number | string;
  prefix?: React.ReactNode;
  suffix?: React.ReactNode;
  valueStyle?: React.CSSProperties;
  subTitle?: React.ReactNode;
  loading?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  prefix,
  suffix,
  valueStyle,
  subTitle,
  loading = false,
}) => {
  return (
    <Card size="small" bodyStyle={{ padding: "10px 14px" }} loading={loading}>
      <Statistic
        title={<span style={{ fontSize: 12, color: "#8c8c8c" }}>{title}</span>}
        value={value}
        prefix={prefix}
        suffix={suffix}
        valueStyle={{ fontSize: 18, fontWeight: 600, fontFamily: "monospace", ...valueStyle }}
      />
      {subTitle && (
        <div style={{ marginTop: 4, fontSize: 11, color: "#8c8c8c" }}>
          {subTitle}
        </div>
      )}
    </Card>
  );
};
