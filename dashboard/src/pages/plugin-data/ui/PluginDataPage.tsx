import React, { useContext, useEffect, useState } from "react";
import { ResourceManagementContext } from "../../../features/manage-template-resources/model/ResourceManagementContext";
import {
  IconFolder,
  IconBolt,
  IconArchive,
  IconDeviceFloppy,
  IconInfoCircle,
} from "@tabler/icons-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../../../shared/ui/tabs";
import { usePluginDataViewModel } from "../model/usePluginDataViewModel";
import { StoredRecordsTab } from "./StoredRecordsTab";
import { ManagedFilesPanel } from "./partitions/ManagedFilesPanel";
import { IncrementalTab } from "./incremental/IncrementalTab";
import { BatchDetailModal } from "./incremental/BatchDetailModal";
import { CheckpointsTab } from "./checkpoints/CheckpointsTab";
import { CheckpointDetailModal } from "./checkpoints/CheckpointDetailModal";
import type { FontManagementRequest } from "../../../features/manage-typst-fonts/model/FontManagementContext";

export const PluginDataPage: React.FC<{
  onNavigate?: (page: "reports" | "config" | "traces") => void;
  fontRequest?: FontManagementRequest | null;
  onFontRequestHandled?: () => void;
}> = ({ onNavigate, fontRequest, onFontRequestHandled }) => {
  const vm = usePluginDataViewModel();
  const [activeTab, setActiveTab] = useState<string>("partitions");
  const resourceRequest = useContext(ResourceManagementContext)?.request;
  useEffect(() => {
    if (resourceRequest) setActiveTab("partitions");
  }, [resourceRequest]);
  useEffect(() => {
    if (fontRequest) setActiveTab("partitions");
  }, [fontRequest]);

  useEffect(() => {
    vm.refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 当切换到增量或检查点 Tab 时按需加载对应数据
  useEffect(() => {
    if (activeTab === "checkpoints") {
      vm.loadCheckpoints();
      vm.refreshCheckpointGroups();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  return (
    <div className="grid min-w-0 gap-6">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="min-w-0">
        <TabsList
          aria-label="数据管理分区"
          className="flex w-fit max-w-full flex-wrap justify-start"
        >
          <TabsTrigger value="partitions">
            <IconFolder aria-hidden="true" />
            存储空间概览
          </TabsTrigger>
          <TabsTrigger value="records">
            <IconArchive aria-hidden="true" />
            分析存档与头像
          </TabsTrigger>
          <TabsTrigger value="incremental">
            <IconBolt aria-hidden="true" />
            增量分析批次
          </TabsTrigger>
          <TabsTrigger value="checkpoints">
            <IconDeviceFloppy aria-hidden="true" />
            阶段产物快照
          </TabsTrigger>
        </TabsList>
        <TabsContent value="partitions">
          <ManagedFilesPanel
            onNavigate={onNavigate}
            onOpenDataTab={setActiveTab}
            fontRequest={fontRequest}
            onFontRequestHandled={onFontRequestHandled}
          />
        </TabsContent>
        <TabsContent value="records">
          <StoredRecordsTab />
        </TabsContent>
        <TabsContent value="incremental">
          <IncrementalTab vm={vm} />
        </TabsContent>
        <TabsContent value="checkpoints">
          <CheckpointsTab vm={vm} />
        </TabsContent>
      </Tabs>
      <div className="flex items-start gap-3 rounded-xl bg-secondary-soft p-4 text-sm text-secondary-ink">
        <IconInfoCircle aria-hidden="true" size={18} className="mt-0.5 shrink-0" />
        <p className="m-0 leading-relaxed">
          字体和素材变更会影响后续渲染；增量批次和快照变更会影响汇总与续跑。操作前请查看对应分区的影响说明。宿主共享临时目录不在本插件管理范围内。
        </p>
      </div>

      {/* 单批次详情 Modal */}
      <BatchDetailModal
        open={vm.batchDetailModalOpen}
        onClose={vm.handleCloseBatchDetail}
        batchDetail={vm.selectedBatchDetail}
        loading={vm.loadingBatchDetail}
        error={vm.batchDetailError}
        onRetry={() => {
          if (vm.selectedBatchDetail) void vm.handleOpenBatchDetail(vm.selectedBatchDetail);
        }}
      />

      {/* 快照 JSON 详情 Modal */}
      <CheckpointDetailModal
        open={vm.ckptDetailModalOpen}
        onClose={vm.handleCloseCkptDetail}
        ckptDetail={vm.selectedCkptDetail}
        loading={vm.loadingCkptDetail}
        error={vm.checkpointDetailError}
        onRetry={() => {
          if (vm.selectedCkptDetail) void vm.handleOpenCkptDetail(vm.selectedCkptDetail);
        }}
      />
    </div>
  );
};
