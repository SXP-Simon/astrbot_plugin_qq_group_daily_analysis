import React, { useEffect, useState } from "react";
import { Card, Space, Alert, Tabs } from "antd";
import {
  FolderOpenOutlined,
  ThunderboltOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { usePluginDataViewModel } from "../model/usePluginDataViewModel";
import { ManagedFilesPanel } from "./partitions/ManagedFilesPanel";
import { IncrementalTab } from "./incremental/IncrementalTab";
import { BatchDetailModal } from "./incremental/BatchDetailModal";
import { CheckpointsTab } from "./checkpoints/CheckpointsTab";
import { CheckpointDetailModal } from "./checkpoints/CheckpointDetailModal";

export const PluginDataPage: React.FC = () => {
  const vm = usePluginDataViewModel();
  const [activeTab, setActiveTab] = useState<string>("partitions");

  useEffect(() => {
    vm.refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 当切换到增量或检查点 Tab 时按需加载对应数据
  useEffect(() => {
    if (activeTab === "incremental") {
      if (vm.selectedIncrGroup) {
        vm.loadIncrementalData(vm.selectedIncrGroup);
      } else if (vm.incrGroups.length > 0) {
        vm.handleSelectIncrGroup(vm.incrGroups[0]);
      }
    } else if (activeTab === "checkpoints") {
      vm.loadCheckpoints();
      vm.refreshCheckpointGroups();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {/* 顶部标签导航切换 */}
      <Card size="small" bodyStyle={{ padding: "8px 12px" }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          size="small"
          items={[
            {
              key: "partitions",
              label: (
                <span>
                  <FolderOpenOutlined /> 存储空间概览
                </span>
              ),
            },
            {
              key: "incremental",
              label: (
                <span>
                  <ThunderboltOutlined /> 增量分析批次 (KV)
                </span>
              ),
            },
            {
              key: "checkpoints",
              label: (
                <span>
                  <SaveOutlined /> 阶段产物快照 (Checkpoints)
                </span>
              ),
            },
          ]}
        />
      </Card>

      {/* 1. 存储空间全景 */}
      {activeTab === "partitions" && <ManagedFilesPanel />}

      {/* 2. 增量分析批次管理 */}
      {activeTab === "incremental" && <IncrementalTab vm={vm} />}

      {/* 3. 阶段产物 Checkpoint 管理 */}
      {activeTab === "checkpoints" && <CheckpointsTab vm={vm} />}

      {/* 底部安全提示 */}
      <Alert
        type="info"
        showIcon
        message="数据管理安全提示"
        description="文件按实际用途提供操作，变更前请查看分区影响说明。字体和素材会影响后续渲染；增量批次和快照会影响分析汇总与续跑。宿主共享临时目录不在本插件管理范围内。"
        style={{ marginTop: 8 }}
      />

      {/* 单批次详情 Modal */}
      <BatchDetailModal
        open={vm.batchDetailModalOpen}
        onClose={vm.handleCloseBatchDetail}
        batchDetail={vm.selectedBatchDetail}
        loading={vm.loadingBatchDetail}
      />

      {/* 快照 JSON 详情 Modal */}
      <CheckpointDetailModal
        open={vm.ckptDetailModalOpen}
        onClose={vm.handleCloseCkptDetail}
        ckptDetail={vm.selectedCkptDetail}
        loading={vm.loadingCkptDetail}
      />
    </Space>
  );
};
