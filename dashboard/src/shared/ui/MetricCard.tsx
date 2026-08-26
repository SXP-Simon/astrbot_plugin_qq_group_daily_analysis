import React from "react";
import { Card, Statistic, Skeleton } from "antd";

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
      style={{ minHeight: 90, height: "100%", display: "flex", flexDirection: "column" }}
      styles={{
        body: {
          padding: "10px 14px",
          height: "100%",
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          boxSizing: "border-box",
        },
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          height: "100%",
          flex: 1,
        }}
      >
        <div style={{ fontSize: 12, color: "#8c8c8c", lineHeight: "18px", marginBottom: 2 }}>
          {title}
        </div>

        {loading ? (
          <div style={{ margin: "3px 0 2px 0" }}>
            <Skeleton.Input active size="small" style={{ width: "70%", height: 22, minWidth: 64, borderRadius: 4 }} />
          </div>
        ) : (
          <Statistic
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
        )}

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
          {loading ? (
            <Skeleton.Input active size="small" style={{ width: "88%", height: 12, borderRadius: 2 }} />
          ) : (
            subTitle || "\u00A0"
          )}
        </div>
      </div>
    </Card>
  );
};
