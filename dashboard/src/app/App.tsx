import React, { useEffect, useRef, useState } from "react";
import { ConfigProvider, Tabs, theme } from "antd";
import {
  DashboardOutlined,
  ApartmentOutlined,
  ExperimentOutlined,
  FolderOpenOutlined,
  FileTextOutlined,
  SettingOutlined,
  HddOutlined,
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
import { LogsPage } from "../pages/logs/ui/LogsPage";
import { useLogsViewModel } from "../pages/logs/model/useLogsViewModel";
import { ConfigPage } from "../pages/config/ui/ConfigPage";
import { useConfigViewModel } from "../pages/config/model/useConfigViewModel";
import { PluginDataPage } from "../pages/plugin-data/ui/PluginDataPage";

import { invalidateTraceCache } from "../entities/trace/api/traceApi";
import { invalidateGroupsCache } from "../entities/group/api/groupApi";

export const App: React.FC = () => {
  const { isDark } = useTheme();
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  const activeTabRef = useRef(activeTab);
  useEffect(() => {
    activeTabRef.current = activeTab;
  }, [activeTab]);

  // ViewModels
  const overviewVM = useOverviewViewModel();
  const tracesVM = useTracesViewModel();
  const contextInsightVM = useContextInsightViewModel();
  const reportsVM = useReportsViewModel();
  const logsVM = useLogsViewModel();
  const configVM = useConfigViewModel(() => {
    handleRefreshAll();
  });

  // 保持最新的 ViewModel 引用，防止 SSE 长监听闭包引用过时的分页/筛选状态
  const viewModelsRef = useRef({
    overviewVM,
    tracesVM,
    contextInsightVM,
    reportsVM,
    logsVM,
  });
  viewModelsRef.current = {
    overviewVM,
    tracesVM,
    contextInsightVM,
    reportsVM,
    logsVM,
  };

  const handleRefreshAll = () => {
    // 显式清理前端冷数据缓存，确保强制刷新时数据 100% 同步
    invalidateTraceCache();
    invalidateGroupsCache();
    overviewVM.refresh(false);
    tracesVM.refresh(false);
    contextInsightVM.refresh(false);
    reportsVM.refresh(false);
    logsVM.refresh(false);
  };

  const triggerVM = useTriggerTask(tracesVM.groups, () => {
    invalidateGroupsCache();
    overviewVM.refresh(true);
    if (activeTabRef.current === "traces") tracesVM.refresh(true);
  });

  // 当 activeTab 切换时，自动将选中的 Tab 元素平滑居中滚动至可视区域中央（防止移动端右侧 Tab 溢出不可见）
  useEffect(() => {
    const timer = setTimeout(() => {
      const activeTabEl = document.querySelector<HTMLElement>(
        `.ant-tabs-tab-active, [data-node-key="${activeTab}"]`
      );
      if (activeTabEl && typeof activeTabEl.scrollIntoView === "function") {
        activeTabEl.scrollIntoView({
          behavior: "smooth",
          inline: "center",
          block: "nearest",
        });
      }
    }, 60);
    return () => clearTimeout(timer);
  }, [activeTab]);

  // SSE 实时事件订阅：纯内存更新任务中间态 + 终态精准无死角同步
  useEffect(() => {
    const unsubscribe = subscribeSSE({
      onMessage: (eventPayload: unknown) => {
        if (!eventPayload || typeof eventPayload !== "object") return;
        const evt = eventPayload as { event?: string; data?: unknown };

        const currentVMs = viewModelsRef.current;

        // 1. 活跃任务状态变更：由 overviewVM 内存增量更新（0 HTTP 请求、0 毫秒延时）
        currentVMs.overviewVM.handleSSEEvent(eventPayload);

        // 2. 终态事件（task_finished）：精准失效该条缓存并仅刷新当前展示的活跃 Tab
        if (evt.event === "task_finished") {
          const data = evt.data as { task_id?: string } | undefined;
          const taskId = data?.task_id;
          if (taskId) {
            invalidateTraceCache(taskId);
          } else {
            invalidateTraceCache();
          }
          invalidateGroupsCache();

          // 仅拉取当前视口激活的 Tab，未激活 Tab 在用户点击切换时再拉取（Lazy Tab Sync）
          const currentTab = activeTabRef.current;
          if (currentTab === "traces") {
            currentVMs.tracesVM.refresh(true);
          } else if (currentTab === "context") {
            currentVMs.contextInsightVM.refresh(true);
          } else if (currentTab === "reports") {
            currentVMs.reportsVM.refresh(true);
          } else if (currentTab === "logs") {
            currentVMs.logsVM.refresh(true);
          }
        }
      },
    });

    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, []);

  const handleViewTrace = (traceId: string) => {
    setSelectedTraceId(traceId);
  };

  const handleTabChange = (key: string) => {
    setActiveTab(key);
    // 标签页按需激活（Lazy Tab Sync）：切换到对应 Tab 时触发该 Tab 的静默刷新
    if (key === "overview") {
      overviewVM.refresh(true);
    } else if (key === "traces") {
      tracesVM.refresh(true);
    } else if (key === "context") {
      contextInsightVM.refresh(true);
    } else if (key === "reports") {
      reportsVM.refresh(true);
    } else if (key === "logs") {
      logsVM.refresh(true);
    }
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
      children: (
        <ContextInsightPage
          viewModel={contextInsightVM}
          onViewTrace={handleViewTrace}
        />
      ),
    },
    {
      key: "reports",
      label: (
        <span>
          <FolderOpenOutlined /> 历史报告
        </span>
      ),
      children: (
        <ReportsPage viewModel={reportsVM} onViewTrace={handleViewTrace} />
      ),
    },
    {
      key: "logs",
      label: (
        <span>
          <FileTextOutlined /> 运行日志
        </span>
      ),
      children: (
        <LogsPage viewModel={logsVM} onViewTrace={handleViewTrace} />
      ),
    },
    {
      key: "config",
      label: (
        <span>
          <SettingOutlined /> 配置中心
        </span>
      ),
      children: <ConfigPage viewModel={configVM} />,
    },
    {
      key: "plugin-data",
      label: (
        <span>
          <HddOutlined /> 数据管理
        </span>
      ),
      children: <PluginDataPage />,
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
            "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
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
          onChange={handleTabChange}
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
          providerId={triggerVM.providerId}
          templateName={triggerVM.templateName}
          submitting={triggerVM.submitting}
          connectedPlatforms={triggerVM.connectedPlatforms}
          loadingPlatforms={triggerVM.loadingPlatforms}
          providers={triggerVM.providers}
          loadingProviders={triggerVM.loadingProviders}
          templates={triggerVM.templates}
          loadingTemplates={triggerVM.loadingTemplates}
          onGroupIdChange={triggerVM.setGroupId}
          onGroupNameChange={triggerVM.setGroupName}
          onPlatformChange={triggerVM.setPlatform}
          onProviderChange={triggerVM.setProviderId}
          onTemplateChange={triggerVM.setTemplateName}
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
