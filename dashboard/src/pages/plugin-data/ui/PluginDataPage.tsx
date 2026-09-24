import React, { useEffect, useState } from "react";
import { Card, Space, Alert, Tabs } from "antd";
import {
  FolderOpenOutlined,
  ThunderboltOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { usePluginDataViewModel } from "../model/usePluginDataViewModel";
import { PartitionsTab } from "./partitions/PartitionsTab";
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
      {activeTab === "partitions" && <PartitionsTab vm={vm} />}

      {/* 2. 增量分析批次管理 */}
      {activeTab === "incremental" && <IncrementalTab vm={vm} />}

      {/* 3. 阶段产物 Checkpoint 管理 */}
      {activeTab === "checkpoints" && <CheckpointsTab vm={vm} />}

      {/* 底部安全提示 */}
      <Alert
        type="info"
        showIcon
        message="数据管理安全提示"
        description="此处展示插件生成的所有离线中间物料与报告数据。清理缓存仅释放本地磁盘占用，已持久化到历史记录数据库的分析摘要与活跃度指标不受影响。"
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
