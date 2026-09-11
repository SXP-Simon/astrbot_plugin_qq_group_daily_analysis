import { useState, useCallback } from "react";
import { message } from "antd";
import {
  fetchPluginDataOverview,
  clearAvatarCache,
  clearReports,
  clearTempFiles,
  clearCustomTemplates,
  clearConfigFiles,
  clearConfigBackups,
  fetchIncrementalGroups,
  fetchIncrementalBatches,
  fetchIncrementalBatchDetail,
  deleteIncrementalBatch,
  resetIncrementalGroup,
  fetchCheckpointGroups,
  fetchCheckpointsList,
  fetchCheckpointDetail,
  deleteCheckpoint,
  PluginDataOverview,
  IncrementalBatchItem,
  IncrementalCursorInfo,
  CheckpointItem,
  CheckpointDetail,
} from "../../../entities/plugin-data/api/pluginDataApi";

const EMPTY_OVERVIEW: PluginDataOverview = {
  avatars: { count: 0, size_bytes: 0 },
  custom_templates: { count: 0, size_bytes: 0 },
  config_files: { count: 0, size_bytes: 0 },
  config_backups: { count: 0, size_bytes: 0 },
  reports: { count: 0, size_bytes: 0 },
  temp_files: { count: 0, size_bytes: 0 },
};

export function usePluginDataViewModel() {
  // 1. 全景概览与存储分区
  const [overview, setOverview] = useState<PluginDataOverview>(EMPTY_OVERVIEW);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [clearing, setClearing] = useState<string | null>(null);

  // 2. 增量分析批次管理
  const [incrGroups, setIncrGroups] = useState<string[]>([]);
  const [selectedIncrGroup, setSelectedIncrGroup] = useState<string>("");
  const [incrBatches, setIncrBatches] = useState<IncrementalBatchItem[]>([]);
  const [incrCursor, setIncrCursor] = useState<IncrementalCursorInfo | null>(null);
  const [loadingIncremental, setLoadingIncremental] = useState(false);
  const [batchDetailModalOpen, setBatchDetailModalOpen] = useState(false);
  const [selectedBatchDetail, setSelectedBatchDetail] = useState<IncrementalBatchItem | null>(null);
  const [loadingBatchDetail, setLoadingBatchDetail] = useState(false);

  // 3. 阶段产物 Checkpoint 管理
  const [ckptGroups, setCkptGroups] = useState<string[]>([]);
  const [ckptFilterGroup, setCkptFilterGroup] = useState<string | undefined>(undefined);
  const [ckptFilterDate, setCkptFilterDate] = useState<string | undefined>(undefined);
  const [ckptFilterStage, setCkptFilterStage] = useState<string | undefined>(undefined);
  const [checkpoints, setCheckpoints] = useState<CheckpointItem[]>([]);
  const [checkpointsTotal, setCheckpointsTotal] = useState(0);
  const [checkpointsPage, setCheckpointsPage] = useState(1);
  const [checkpointsPageSize, setCheckpointsPageSize] = useState(20);
  const [loadingCheckpoints, setLoadingCheckpoints] = useState(false);
  const [ckptDetailModalOpen, setCkptDetailModalOpen] = useState(false);
  const [selectedCkptDetail, setSelectedCkptDetail] = useState<CheckpointDetail | null>(null);
  const [loadingCkptDetail, setLoadingCkptDetail] = useState(false);

  // 刷新存储概览
  const refreshOverview = useCallback(async () => {
    setLoadingOverview(true);
    try {
      const data = await fetchPluginDataOverview();
      setOverview(data);
    } catch {
      message.error("加载数据概览失败");
    } finally {
      setLoadingOverview(false);
    }
  }, []);

  // 清理指定存储分区
  const runClear = async (
    key: string,
    fn: () => Promise<number>,
    label: string
  ) => {
    setClearing(key);
    try {
      const deleted = await fn();
      message.success(`已清除 ${deleted} 个${label}文件`);
      await refreshOverview();
    } catch {
      message.error(`清除${label}失败`);
    } finally {
      setClearing(null);
    }
  };

  // 刷新增量群列表
  const refreshIncrGroups = useCallback(async () => {
    try {
      const groups = await fetchIncrementalGroups();
      setIncrGroups(groups);
      setSelectedIncrGroup((current) => {
        if (current && groups.includes(current)) return current;
        return groups[0] || "";
      });
    } catch {
      message.error("获取增量群列表失败");
    }
  }, []);

  // 加载指定群的增量批次与游标
  const loadIncrementalData = useCallback(async (groupId: string) => {
    if (!groupId) {
      setIncrBatches([]);
      setIncrCursor(null);
      return;
    }
    setLoadingIncremental(true);
    try {
      const res = await fetchIncrementalBatches(groupId);
      if (res) {
        setIncrBatches(res.batches || []);
        setIncrCursor(res.cursor || null);
      } else {
        setIncrBatches([]);
        setIncrCursor(null);
      }
    } catch {
      message.error(`加载群 ${groupId} 增量批次失败`);
    } finally {
      setLoadingIncremental(false);
    }
  }, []);

  // 切换选中的增量群
  const handleSelectIncrGroup = (groupId: string) => {
    setSelectedIncrGroup(groupId);
    loadIncrementalData(groupId);
  };

  // 查看单条增量批次详情
  const handleOpenBatchDetail = async (item: IncrementalBatchItem) => {
    setBatchDetailModalOpen(true);
    setSelectedBatchDetail(item);
    setLoadingBatchDetail(true);
    try {
      const full = await fetchIncrementalBatchDetail(item.group_id, item.batch_id);
      if (full) {
        setSelectedBatchDetail(full);
      }
    } catch {
      message.error("获取批次详细数据失败");
    } finally {
      setLoadingBatchDetail(false);
    }
  };

  const handleCloseBatchDetail = () => {
    setBatchDetailModalOpen(false);
    setSelectedBatchDetail(null);
  };

  // 删除单条增量批次
  const handleDeleteBatch = async (groupId: string, batchId: string) => {
    try {
      const ok = await deleteIncrementalBatch(groupId, batchId);
      if (ok) {
        message.success(`已成功删除批次 ${batchId}`);
        await loadIncrementalData(groupId);
        await refreshOverview();
      } else {
        message.error("删除批次失败：批次不存在或已被移除");
      }
    } catch {
      message.error("删除批次异常");
    }
  };

  // 重置指定群的所有增量批次与游标
  const handleResetIncrGroup = async (groupId: string) => {
    try {
      const res = await resetIncrementalGroup(groupId);
      message.success(`已重置群 ${groupId} 增量状态，清理了 ${res.deleted_batches} 个批次`);
      await loadIncrementalData(groupId);
      await refreshIncrGroups();
      await refreshOverview();
    } catch {
      message.error("重置群增量状态异常");
    }
  };

  // 刷新 Checkpoint 群列表与列表
  const refreshCheckpointGroups = useCallback(async () => {
    try {
      const groups = await fetchCheckpointGroups();
      setCkptGroups(groups);
    } catch {
      message.error("获取 Checkpoint 群号列表失败");
    }
  }, []);

  const loadCheckpoints = useCallback(
    async (
      page = checkpointsPage,
      pageSize = checkpointsPageSize,
      group = ckptFilterGroup,
      date = ckptFilterDate,
      stage = ckptFilterStage
    ) => {
      setLoadingCheckpoints(true);
      try {
        const offset = (page - 1) * pageSize;
        const res = await fetchCheckpointsList({
          limit: pageSize,
          offset,
          group_id: group,
          date_str: date,
          stage_name: stage,
        });
        setCheckpoints(res.items || []);
        setCheckpointsTotal(res.total || 0);
        setCheckpointsPage(page);
        setCheckpointsPageSize(pageSize);
      } catch {
        message.error("加载阶段快照列表失败");
      } finally {
        setLoadingCheckpoints(false);
      }
    },
    [checkpointsPage, checkpointsPageSize, ckptFilterGroup, ckptFilterDate, ckptFilterStage]
  );

  // 查看 Checkpoint JSON 详情
  const handleOpenCkptDetail = async (item: CheckpointItem) => {
    setCkptDetailModalOpen(true);
    setSelectedCkptDetail({
      checkpoint_id: item.checkpoint_id,
      group_id: item.group_id,
      date_str: item.date_str,
      stage_name: item.stage_name,
      created_at: item.created_at,
      created_at_formatted: item.created_at_formatted,
      data_size_bytes: item.data_size_bytes ?? item.data_size,
      data: null,
    });
    setLoadingCkptDetail(true);
    try {
      const detail = await fetchCheckpointDetail(
        item.group_id,
        item.date_str,
        item.stage_name
      );
      if (detail) {
        const payloadData =
          detail.checkpoint_data !== undefined
            ? detail.checkpoint_data
            : detail.data !== undefined
            ? detail.data
            : detail;
        setSelectedCkptDetail({
          checkpoint_id: detail.checkpoint_id || item.checkpoint_id,
          group_id: detail.group_id || item.group_id,
          date_str: detail.date_str || item.date_str,
          stage_name: detail.stage_name || item.stage_name,
          created_at: detail.created_at ?? item.created_at,
          created_at_formatted:
            detail.created_at_formatted || item.created_at_formatted,
          data_size_bytes:
            detail.data_size_bytes ?? detail.data_size ?? item.data_size_bytes,
          data: payloadData,
        });
      } else {
        message.error("快照数据不存在或已过期");
      }
    } catch {
      message.error("获取快照详情异常");
    } finally {
      setLoadingCkptDetail(false);
    }
  };

  const handleCloseCkptDetail = () => {
    setCkptDetailModalOpen(false);
    setSelectedCkptDetail(null);
  };

  // 删除 Checkpoint
  const handleDeleteCheckpoint = async (
    groupId: string,
    dateStr: string,
    stageName?: string
  ) => {
    try {
      const ok = await deleteCheckpoint(groupId, dateStr, stageName);
      if (ok) {
        message.success(
          stageName
            ? `已删除 ${groupId} (${dateStr}) 的阶段快照「${stageName}」`
            : `已清空 ${groupId} (${dateStr}) 的所有阶段快照`
        );
        await loadCheckpoints();
        await refreshCheckpointGroups();
        await refreshOverview();
      } else {
        message.error("删除快照失败");
      }
    } catch {
      message.error("删除快照异常");
    }
  };

  // 全局刷新
  const refreshAll = useCallback(async () => {
    await Promise.all([
      refreshOverview(),
      refreshIncrGroups(),
      refreshCheckpointGroups(),
    ]);
  }, [refreshOverview, refreshIncrGroups, refreshCheckpointGroups]);

  return {
    // 1. 全景
    overview,
    loadingOverview,
    clearing,
    refreshOverview,
    clearAvatarCache: () => runClear("avatars", clearAvatarCache, "头像缓存"),
    clearReports: () => runClear("reports", clearReports, "历史报告"),
    clearTempFiles: () => runClear("temp_files", clearTempFiles, "临时渲染缓存"),
    clearCustomTemplates: () =>
      runClear("custom_templates", clearCustomTemplates, "自定义报告模板"),
    clearConfigFiles: () =>
      runClear("config_files", clearConfigFiles, "配置参考素材"),
    clearConfigBackups: () =>
      runClear("config_backups", clearConfigBackups, "配置历史自动备份"),

    // 2. 增量
    incrGroups,
    selectedIncrGroup,
    incrBatches,
    incrCursor,
    loadingIncremental,
    batchDetailModalOpen,
    selectedBatchDetail,
    loadingBatchDetail,
    refreshIncrGroups,
    loadIncrementalData,
    handleSelectIncrGroup,
    handleOpenBatchDetail,
    handleCloseBatchDetail,
    handleDeleteBatch,
    handleResetIncrGroup,

    // 3. 快照 Checkpoints
    ckptGroups,
    ckptFilterGroup,
    ckptFilterDate,
    ckptFilterStage,
    checkpoints,
    checkpointsTotal,
    checkpointsPage,
    checkpointsPageSize,
    loadingCheckpoints,
    ckptDetailModalOpen,
    selectedCkptDetail,
    loadingCkptDetail,
    setCkptFilterGroup,
    setCkptFilterDate,
    setCkptFilterStage,
    loadCheckpoints,
    refreshCheckpointGroups,
    handleOpenCkptDetail,
    handleCloseCkptDetail,
    handleDeleteCheckpoint,

    // 总刷新
    refreshAll,
  };
}
