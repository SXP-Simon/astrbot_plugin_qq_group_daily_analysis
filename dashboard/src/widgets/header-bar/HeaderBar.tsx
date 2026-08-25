import React from "react";
import { Typography, Space, Tag, Button } from "antd";
import {
  RobotOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
} from "@ant-design/icons";

const { Title } = Typography;

interface HeaderBarProps {
  isDark: boolean;
  onRefresh: () => void;
  onOpenTrigger: () => void;
  loading?: boolean;
}

export const HeaderBar: React.FC<HeaderBarProps> = ({
  isDark,
  onRefresh,
  onOpenTrigger,
  loading = false,
}) => {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 16px",
        background: isDark ? "#141414" : "#ffffff",
        borderBottom: `1px solid ${isDark ? "#303030" : "#f0f0f0"}`,
        marginBottom: 12,
      }}
    >
      <Space align="center" size="middle">
        <RobotOutlined style={{ fontSize: 20, color: "#1677ff" }} />
        <div>
          <Space align="center" size="small">
            <Title level={5} style={{ margin: 0, fontSize: 15 }}>
              QQ群日常分析控制台
            </Title>
            <Tag color="blue" className="font-mono text-xs">
              v4.25 Agent Infra
            </Tag>
          </Space>
          <div style={{ fontSize: 11, color: "#8c8c8c", marginTop: 2 }}>
            基于 dsh-context 上下文洞察与 SQLite 全链路执行追踪
          </div>
        </div>
      </Space>

      <Space size="small">
        <Button
          size="small"
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={onOpenTrigger}
        >
          手动触发分析
        </Button>
        <Button
          size="small"
          icon={<ReloadOutlined spin={loading} />}
          onClick={onRefresh}
        >
          刷新
        </Button>
      </Space>
    </div>
  );
};
