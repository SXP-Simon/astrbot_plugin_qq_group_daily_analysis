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
    <Card
      size="small"
      style={{ minHeight: 88, height: "100%", display: "flex", flexDirection: "column" }}
      bodyStyle={{
        padding: "10px 14px",
        height: "100%",
        flex: 1,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          opacity: loading ? 0.6 : 1,
          transition: "opacity 0.2s ease-in-out",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          height: "100%",
          flex: 1,
        }}
      >
        <Statistic
          title={<span style={{ fontSize: 12, color: "#8c8c8c", lineHeight: "18px" }}>{title}</span>}
          value={value}
          prefix={prefix}
          suffix={suffix}
          valueStyle={{
            fontSize: 18,
            fontWeight: 600,
            fontFamily: "monospace",
            lineHeight: "24px",
            ...valueStyle,
          }}
        />
        <div
          style={{
            marginTop: 4,
            fontSize: 11,
            color: "#8c8c8c",
            lineHeight: "16px",
            minHeight: 16,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {subTitle || "\u00A0"}
        </div>
      </div>
    </Card>
  );
};
