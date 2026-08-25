import React from "react";
import { Tag } from "antd";

interface StatusTagProps {
  status: "succeeded" | "failed" | "running" | "aborted" | string;
}

export const StatusTag: React.FC<StatusTagProps> = ({ status }) => {
  switch (status) {
    case "succeeded":
      return (
        <Tag color="success" className="font-mono text-xs font-semibold">
          SUCCEEDED
        </Tag>
      );
    case "failed":
      return (
        <Tag color="error" className="font-mono text-xs font-semibold">
          FAILED
        </Tag>
      );
    case "running":
      return (
        <Tag color="processing" className="font-mono text-xs font-semibold">
          RUNNING
        </Tag>
      );
    case "aborted":
      return (
        <Tag color="default" className="font-mono text-xs font-semibold">
          ABORTED
        </Tag>
      );
    default:
      return (
        <Tag className="font-mono text-xs">
          {String(status).toUpperCase()}
        </Tag>
      );
  }
};
