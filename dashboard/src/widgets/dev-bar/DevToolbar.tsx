import React, { useState } from "react";
import { Button, Tag, Space, Dropdown, MenuProps, message } from "antd";
import {
  ToolOutlined,
  BulbOutlined,
  ApiOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import { getDevBridgeMode, setDevBridgeMode } from "../../shared/api/devBridge";
import { mockSSEService } from "../../mocks";

export const DevToolbar: React.FC = () => {
  const [mode, setMode] = useState(getDevBridgeMode());

  // 生产环境或处于 AstrBot 宿主 iframe 内时不渲染
  if (!import.meta.env.DEV || (typeof window !== "undefined" && window.AstrBotPluginPage)) {
    return null;
  }

  const handleToggleTheme = () => {
    const current = localStorage.getItem("astrbot_plugin_theme_is_dark") === "true";
    const next = !current;
    localStorage.setItem("astrbot_plugin_theme_is_dark", String(next));
    window.location.reload();
  };

  const handleModeChange = (newMode: "mock" | "proxy") => {
    setMode(newMode);
    setDevBridgeMode(newMode);
  };

  const handleTriggerMockSSE = () => {
    mockSSEService.emitManualEvent({
      type: "TASK_UPDATE",
      event: "task_progress",
      data: {
        task_id: "task-live-demo-manual",
        trace_id: `trace-manual-${Date.now()}`,
        group_id: "123456789",
        stage: "llm_analysis",
        progress: 85,
        elapsed_seconds: 15,
      },
    });
    message.success("已向前端注入模拟 SSE 阶段事件");
  };

  const menuItems: MenuProps["items"] = [
    {
      key: "mode-mock",
      icon: <CheckCircleOutlined />,
      label: (
        <span>
          Mock 模式 {mode === "mock" && <Tag color="blue">当前</Tag>}
        </span>
      ),
      onClick: () => handleModeChange("mock"),
    },
    {
      key: "mode-proxy",
      icon: <ApiOutlined />,
      label: (
        <span>
          Proxy 直连后端 (:6185) {mode === "proxy" && <Tag color="blue">当前</Tag>}
        </span>
      ),
      onClick: () => handleModeChange("proxy"),
    },
    {
      type: "divider",
    },
    {
      key: "theme",
      icon: <BulbOutlined />,
      label: "切换亮色 / 暗黑主题",
      onClick: handleToggleTheme,
    },
    {
      key: "sse",
      icon: <ThunderboltOutlined />,
      label: "注入测试 SSE 任务事件",
      onClick: handleTriggerMockSSE,
    },
  ];

  return (
    <div
      style={{
        position: "fixed",
        bottom: 16,
        right: 16,
        zIndex: 9999,
        background: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(8px)",
        padding: "6px 12px",
        borderRadius: 20,
        boxShadow: "0 4px 12px rgba(0, 0, 0, 0.25)",
      }}
    >
      <Space size={8}>
        <Tag color={mode === "mock" ? "purple" : "green"} style={{ margin: 0 }}>
          {mode === "mock" ? "DEV: MOCK" : "DEV: PROXY (:6185)"}
        </Tag>
        <Dropdown menu={{ items: menuItems }} placement="topRight">
          <Button
            type="text"
            size="small"
            icon={<ToolOutlined style={{ color: "#fff" }} />}
            style={{ color: "#fff", padding: "0 4px" }}
          >
            开发工具箱
          </Button>
        </Dropdown>
      </Space>
    </div>
  );
};
