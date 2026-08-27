import React from "react";
import { Tag } from "antd";

interface StatusTagProps {
  status: "succeeded" | "failed" | "running" | "aborted" | string;
}

export const StatusTag: React.FC<StatusTagProps> = ({ status }) => {
  switch (status) {
    case "succeeded":
      return (
        <Tag color="success" className="text-xs font-semibold">
          成功
        </Tag>
      );
    case "warning":
    case "partial_success":
      return (
        <Tag color="warning" className="text-xs font-semibold">
          部分成功
        </Tag>
      );
    case "failed":
      return (
        <Tag color="error" className="text-xs font-semibold">
          失败
        </Tag>
      );
    case "running":
      return (
        <Tag color="processing" className="text-xs font-semibold">
          运行中
        </Tag>
      );
    case "aborted":
      return (
        <Tag color="default" className="text-xs font-semibold">
          已中止
        </Tag>
      );
    default:
      return (
        <Tag className="text-xs">
          {String(status)}
        </Tag>
      );
  }
};
