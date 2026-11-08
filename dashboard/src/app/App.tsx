import React, { useEffect, useRef, useState } from "react";
import {
  IconLayoutDashboard,
  IconStack2,
  IconChartBar,
  IconFileText,
  IconSettings,
  IconFolder,
  IconTerminal2,
} from "@tabler/icons-react";
import { AppShell } from "./ui/AppShell";
import { Toaster } from "../shared/ui/sonner";
import { usePageNavigation } from "./model/usePageNavigation";
import { subscribeSSE } from "../shared/api/bridge";
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
import { DevToolbar } from "../widgets/dev-bar/DevToolbar";
import {
  FontManagementContext,
  type FontManagementRequest,
} from "../features/manage-typst-fonts/model/FontManagementContext";
import {
  ResourceManagementContext,
  type ResourceManagementRequest,
} from "../features/manage-template-resources/model/ResourceManagementContext";

import { invalidateTraceCache } from "../entities/trace/api/traceApi";
import { invalidateGroupsCache } from "../entities/group/api/groupApi";

export const App: React.FC = () => {
  const { page: activeTab, visited, navigate } = usePageNavigation("overview");
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [fontRequest, setFontRequest] = useState<FontManagementRequest | null>(null);
  const [fontVersion, setFontVersion] = useState(0);
  const fontNavigationSequence = useRef(0);
  const [resourceRequest, setResourceRequest] = useState<ResourceManagementRequest | null>(null);
  const [resourceVersion, setResourceVersion] = useState(0);
  const resourceNavigationSequence = useRef(0);

  const activeTabRef = useRef(activeTab);
  useEffect(() => {
    activeTabRef.current = activeTab;
  }, [activeTab]);

  // ViewModels
  const overviewVM = useOverviewViewModel(activeTab === "overview");
  const tracesVM = useTracesViewModel();
  const contextInsightVM = useContextInsightViewModel();
  const reportsVM = useReportsViewModel();
  const logsVM = useLogsViewModel(activeTab === "logs");
  const configVM = useConfigViewModel(() => {
    handleRefreshAll();
  });

  useEffect(() => {
    // 宿主沙盒没有离开确认接口；仅为独立页面注册浏览器的刷新、关闭提醒。
    if (!configVM.isDirty || window.parent !== window) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [configVM.isDirty]);

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

  // SSE 实时事件订阅：纯内存更新任务中间态 + 终态精准无死角同步
  useEffect(() => {
    const unsubscribe = subscribeSSE({
      onMessage: (eventPayload: unknown) => {
        if (!eventPayload || typeof eventPayload !== "object") return;
        const evt = eventPayload as { event?: string; data?: unknown };

        const currentVMs = viewModelsRef.current;

        // 1. 活跃任务状态变更：由 overviewVM 内存增量更新（0 HTTP 请求、0 毫秒延时）
        currentVMs.overviewVM.handleSSEEvent(eventPayload);

        // 2. 完成、取消和超时均为终态：精准失效缓存并刷新当前展示的 Tab。
        if (["task_finished", "task_canceled", "task_timed_out"].includes(evt.event ?? "")) {
          const data = evt.data as { task_id?: string } | undefined;
          const taskId = data?.task_id;
          if (taskId) {
            invalidateTraceCache(taskId);
          } else {
            invalidateTraceCache();
          }
          invalidateGroupsCache();

          // 历史列表保留阅读位置，只标记更新；用户主动刷新时才重新查询和排序。
          currentVMs.tracesVM.markUpdated();
          currentVMs.contextInsightVM.markUpdated();
          currentVMs.reportsVM.markUpdated();
          if (activeTabRef.current === "logs") currentVMs.logsVM.refresh(true);
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
    activeTabRef.current = key;
    navigate(key);
    // 总览和日志按需同步；历史列表保留分页与选择，更新由用户确认。
    if (key === "overview") {
      overviewVM.refresh(true);
    } else if (key === "logs") {
      logsVM.refresh(true);
    }
  };

  const tabItems = [
    {
      key: "overview",
      label: "总览",
      icon: <IconLayoutDashboard aria-hidden="true" />,
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
      label: "分析记录",
      icon: <IconStack2 aria-hidden="true" />,
      children: <TracesPage viewModel={tracesVM} onViewTrace={handleViewTrace} />,
    },
    {
      key: "context",
      label: "统计",
      icon: <IconChartBar aria-hidden="true" />,
      children: <ContextInsightPage viewModel={contextInsightVM} onViewTrace={handleViewTrace} />,
    },
    {
      key: "reports",
      label: "报告",
      icon: <IconFileText aria-hidden="true" />,
      children: <ReportsPage viewModel={reportsVM} onViewTrace={handleViewTrace} />,
    },
    {
      key: "logs",
      label: "日志",
      icon: <IconTerminal2 aria-hidden="true" />,
      children: <LogsPage viewModel={logsVM} onViewTrace={handleViewTrace} />,
    },
    {
      key: "config",
      label: "配置",
      icon: <IconSettings aria-hidden="true" />,
      children: <ConfigPage viewModel={configVM} />,
    },
    {
      key: "plugin-data",
      label: "数据",
      icon: <IconFolder aria-hidden="true" />,
      children: (
        <PluginDataPage
          onNavigate={handleTabChange}
          fontRequest={fontRequest}
          onFontRequestHandled={() => setFontRequest(null)}
        />
      ),
    },
  ];

  return (
    <FontManagementContext.Provider
      value={{
        open: (selection) => {
          setFontRequest({ ...selection, sequence: ++fontNavigationSequence.current });
          handleTabChange("plugin-data");
        },
        changed: () => setFontVersion((value) => value + 1),
        version: fontVersion,
      }}
    >
      <ResourceManagementContext.Provider
        value={{
          open: (selection) => {
            setResourceRequest({ ...selection, sequence: ++resourceNavigationSequence.current });
            handleTabChange("plugin-data");
          },
          request: resourceRequest,
          handled: () => setResourceRequest(null),
          changed: () => setResourceVersion((value) => value + 1),
          version: resourceVersion,
        }}
      >
        <div>
          <Toaster />
          <AppShell
            activePage={activeTab}
            visited={visited}
            onNavigate={handleTabChange}
            items={tabItems}
            onRefresh={handleRefreshAll}
            onOpenTrigger={triggerVM.handleOpen}
            loading={overviewVM.loading}
            configDirty={configVM.isDirty}
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
            templatesError={triggerVM.templatesError}
            optionsError={triggerVM.optionsError}
            onRefreshOptions={triggerVM.refreshOptions}
            onRefreshTemplates={() => void triggerVM.refreshTemplates()}
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

          {/* 独立开发调试浮动工具栏 (Dev Only) */}
          {import.meta.env.DEV && <DevToolbar />}
        </div>
      </ResourceManagementContext.Provider>
    </FontManagementContext.Provider>
  );
};
