import React from "react";
import { Typography, Space, Button } from "antd";
import {
  ReloadOutlined,
  PlayCircleOutlined,
} from "@ant-design/icons";
import logoImg from "../../shared/assets/logo.png";

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
        <img
          src={logoImg}
          alt="Logo"
          style={{
            width: 28,
            height: 28,
            borderRadius: 6,
            objectFit: "contain",
            display: "block",
          }}
        />
        <div>
          <Title level={5} style={{ margin: 0, fontSize: 15 }}>
            QQ群日常分析控制台
          </Title>
          <div style={{ fontSize: 11, color: "#8c8c8c", marginTop: 2 }}>
            查看群聊分析记录、执行进度与大模型消耗统计
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
