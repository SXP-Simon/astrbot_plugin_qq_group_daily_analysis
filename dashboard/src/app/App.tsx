import React, { useEffect, useState } from "react";
import { ConfigProvider, Tabs, theme } from "antd";
import {
  DashboardOutlined,
  ApartmentOutlined,
  ExperimentOutlined,
  FolderOpenOutlined,
} from "@ant-design/icons";
import { subscribeSSE } from "../shared/api/bridge";
import { useTheme } from "../shared/lib/useTheme";
import { HeaderBar } from "../widgets/header-bar/HeaderBar";
import { TraceDrawer } from "../widgets/trace-drawer/TraceDrawer";
import { TriggerTaskModal } from "../features/trigger-task/ui/TriggerTaskModal";
import { useTriggerTask } from "../features/trigger-task/model/useTriggerTask";
import { OverviewPage } from "../pages/overview/ui/OverviewPage";
import { useOverviewViewModel } from "../pages/overview/model/useOverviewViewModel";
import { TracesPage } from "../pages/traces/ui/TracesPage";
import { useTracesViewModel } from "../pages/traces/model/useTracesViewModel";
import { ContextInsightPage } from "../pages/context-insight/ui/ContextInsightPage";
import { useContextInsightViewModel } from "../pages/context-insight/model/useContextInsightViewModel";
import { ReportsPage } from "../pages/reports/ui/ReportsPage";
import { useReportsViewModel } from "../pages/reports/model/useReportsViewModel";

import { invalidateTraceCache } from "../entities/trace/api/traceApi";
import { invalidateGroupsCache } from "../entities/group/api/groupApi";

export const App: React.FC = () => {
  const { isDark } = useTheme();
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  // ViewModels
  const overviewVM = useOverviewViewModel();
  const tracesVM = useTracesViewModel();
  const contextInsightVM = useContextInsightViewModel();
  const reportsVM = useReportsViewModel();

  const handleRefreshAll = () => {
    // 显式清理前端冷数据缓存，确保强制刷新时数据 100% 同步
    invalidateTraceCache();
    invalidateGroupsCache();
    overviewVM.refresh();
    tracesVM.refresh();
    contextInsightVM.refresh();
    reportsVM.refresh();
  };

  const triggerVM = useTriggerTask(() => {
    invalidateGroupsCache();
    overviewVM.refresh();
    tracesVM.refresh();
  });

  // SSE 实时事件订阅：接收到后端任务状态变更时精准失效相关缓存
  useEffect(() => {
    const unsubscribe = subscribeSSE({
      onMessage: (eventPayload: unknown) => {
        // 若有具体 task_id 变更，失效该条目的不可变缓存
        if (eventPayload && typeof eventPayload === "object" && "data" in eventPayload) {
          const data = (eventPayload as { data?: { task_id?: string } }).data;
          if (data?.task_id) {
            invalidateTraceCache(data.task_id);
          }
        } else {
          invalidateTraceCache();
        }
        invalidateGroupsCache();
        overviewVM.refresh();
        tracesVM.refresh();
        contextInsightVM.refresh();
        reportsVM.refresh();
      },
    });

    return () => {
      if (unsubscribe) unsubscribe();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleViewTrace = (traceId: string) => {
    setSelectedTraceId(traceId);
  };

  const tabItems = [
    {
      key: "overview",
      label: (
        <span>
          <DashboardOutlined /> 运行总览
        </span>
      ),
      children: (
        <OverviewPage
          viewModel={overviewVM}
          onOpenTrigger={triggerVM.handleOpen}
          onViewTrace={handleViewTrace}
        />
      ),
    },
    {
      key: "traces",
      label: (
        <span>
          <ApartmentOutlined /> 分析记录
        </span>
      ),
      children: (
        <TracesPage
          viewModel={tracesVM}
          onViewTrace={handleViewTrace}
        />
      ),
    },
    {
      key: "context",
      label: (
        <span>
          <ExperimentOutlined /> 统计与消耗
        </span>
      ),
      children: <ContextInsightPage viewModel={contextInsightVM} />,
    },
    {
      key: "reports",
      label: (
        <span>
          <FolderOpenOutlined /> 历史报告
        </span>
      ),
      children: <ReportsPage viewModel={reportsVM} />,
    },
  ];

  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: "#1677ff",
          borderRadius: 4,
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
          fontFamilyCode:
            "SFMono-Regular, Consolas, 'Liberation Mono', Menlo, Courier, monospace",
        },
      }}
    >
      <div
        style={{
          minHeight: "100vh",
          background: isDark ? "#000000" : "#f5f5f5",
          padding: 12,
          color: isDark ? "#ffffff" : "#000000",
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
        }}
      >
        {/* 顶部 HeaderBar 微件 */}
        <HeaderBar
          isDark={isDark}
          onRefresh={handleRefreshAll}
          onOpenTrigger={triggerVM.handleOpen}
          loading={overviewVM.loading}
        />

        {/* 核心 Tab 导航与页面路由 */}
        <Tabs
          activeKey={activeTab}
          onChange={(key) => {
            setActiveTab(key);
            if (key === "overview") overviewVM.refresh();
            else if (key === "traces") tracesVM.refresh();
            else if (key === "context") contextInsightVM.refresh();
            else if (key === "reports") reportsVM.refresh();
          }}
          items={tabItems}
          type="card"
          size="small"
        />

        {/* 触发任务模态框 (Feature) */}
        <TriggerTaskModal
          open={triggerVM.open}
          groupId={triggerVM.groupId}
          groupName={triggerVM.groupName}
          platform={triggerVM.platform}
          submitting={triggerVM.submitting}
          onGroupIdChange={triggerVM.setGroupId}
          onGroupNameChange={triggerVM.setGroupName}
          onPlatformChange={triggerVM.setPlatform}
          onClose={triggerVM.handleClose}
          onSubmit={triggerVM.handleSubmit}
        />

        {/* 链路追溯抽屉 (Widget) */}
        <TraceDrawer
          traceId={selectedTraceId}
          open={!!selectedTraceId}
          onClose={() => setSelectedTraceId(null)}
        />
      </div>
    </ConfigProvider>
  );
};
