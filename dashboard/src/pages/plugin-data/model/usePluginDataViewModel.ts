import { useState, useCallback, useRef, useEffect } from "react";
import { toast } from "sonner";
import {
  fetchIncrementalGroups,
  fetchIncrementalBatches,
  fetchIncrementalBatchDetail,
  deleteIncrementalBatch,
  resetIncrementalGroup,
  fetchCheckpointGroups,
  fetchCheckpointsList,
  fetchCheckpointDetail,
  deleteCheckpoint,
  IncrementalBatchItem,
  IncrementalCursorInfo,
  CheckpointItem,
  CheckpointDetail,
} from "../../../entities/plugin-data/api/pluginDataApi";

export function usePluginDataViewModel() {
  // 2. 增量分析批次管理
  const [incrGroups, setIncrGroups] = useState<string[]>([]);
  const [selectedIncrGroup, setSelectedIncrGroup] = useState<string>("");
  const [incrBatches, setIncrBatches] = useState<IncrementalBatchItem[]>([]);
  const [incrCursor, setIncrCursor] = useState<IncrementalCursorInfo | null>(null);
  const [loadingIncremental, setLoadingIncremental] = useState(false);
  const [batchDetailModalOpen, setBatchDetailModalOpen] = useState(false);
  const [selectedBatchDetail, setSelectedBatchDetail] = useState<IncrementalBatchItem | null>(null);
  const [loadingBatchDetail, setLoadingBatchDetail] = useState(false);
  const [batchDetailError, setBatchDetailError] = useState("");
  const batchDetailRequest = useRef(0);
  const incrementalRequest = useRef(0);
  const groupsRequest = useRef(0);
  const currentGroup = useRef("");
  const mounted = useRef(true);
  const mutationLock = useRef(false);
  const [incrementalError, setIncrementalError] = useState("");
  const [incrGroupsError, setIncrGroupsError] = useState("");
  const [incrementalMutationError, setIncrementalMutationError] = useState("");
  const [incrementalBusy, setIncrementalBusy] = useState(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      batchDetailRequest.current += 1;
      incrementalRequest.current += 1;
      groupsRequest.current += 1;
    };
  }, []);

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

  // 刷新增量群列表
  const refreshIncrGroups = useCallback(async () => {
    const request = ++groupsRequest.current;
    setIncrGroupsError("");
    try {
      const groups = await fetchIncrementalGroups();
      if (request !== groupsRequest.current) return;
      setIncrGroups(groups);
      setSelectedIncrGroup((current) => {
        if (current && groups.includes(current)) return current;
        return groups[0] || "";
      });
    } catch {
      if (request === groupsRequest.current) setIncrGroupsError("群聊列表读取失败，请刷新重试。");
    }
  }, []);

  // 切群和卸载立即废弃旧请求，同群刷新失败时保留上次记录。
  const loadIncrementalData = useCallback(async (groupId: string) => {
    if (!groupId || currentGroup.current !== groupId) return;
    const request = ++incrementalRequest.current;
    setLoadingIncremental(true);
    setIncrementalError("");
    try {
      const res = await fetchIncrementalBatches(groupId);
      if (request !== incrementalRequest.current || currentGroup.current !== groupId) return;
      if (
        res &&
        (res.group_id !== groupId ||
          res.cursor.group_id !== groupId ||
          res.batches.some((batch) => batch.group_id !== groupId))
      )
        throw new Error("批次群聊不一致");
      setIncrBatches(res?.batches ?? []);
      setIncrCursor(res?.cursor ?? null);
    } catch {
      if (request === incrementalRequest.current)
        setIncrementalError("增量批次读取失败，请刷新重试；已有记录保持不变。");
    } finally {
      if (request === incrementalRequest.current) setLoadingIncremental(false);
    }
  }, []);

  useEffect(() => {
    currentGroup.current = selectedIncrGroup;
    incrementalRequest.current += 1;
    setIncrBatches([]);
    setIncrCursor(null);
    setIncrementalError("");
    setLoadingIncremental(false);
    if (selectedIncrGroup) void loadIncrementalData(selectedIncrGroup);
  }, [selectedIncrGroup, loadIncrementalData]);

  const handleSelectIncrGroup = (groupId: string) => {
    currentGroup.current = groupId;
    incrementalRequest.current += 1;
    setSelectedIncrGroup(groupId);
  };

  // 请求编号同时隔离切换、关闭与卸载后的迟到响应。
  const handleOpenBatchDetail = async (item: IncrementalBatchItem) => {
    const request = ++batchDetailRequest.current;
    setBatchDetailModalOpen(true);
    setSelectedBatchDetail(item);
    setLoadingBatchDetail(true);
    setBatchDetailError("");
    try {
      const full = await fetchIncrementalBatchDetail(item.group_id, item.batch_id);
      if (request !== batchDetailRequest.current) return;
      if (!full) {
        setBatchDetailError("这个批次已不存在，请刷新列表。");
      } else if (full.group_id !== item.group_id || full.batch_id !== item.batch_id) {
        setBatchDetailError("返回的批次与所选记录不一致，请重新读取。");
      } else {
        setSelectedBatchDetail(full);
      }
    } catch {
      if (request === batchDetailRequest.current)
        setBatchDetailError("批次详情读取失败，请检查连接后重试。");
    } finally {
      if (request === batchDetailRequest.current) setLoadingBatchDetail(false);
    }
  };

  const handleCloseBatchDetail = () => {
    batchDetailRequest.current += 1;
    setBatchDetailModalOpen(false);
    setSelectedBatchDetail(null);
    setLoadingBatchDetail(false);
    setBatchDetailError("");
  };

  // 确认弹窗持有操作目标；完成后只刷新仍在查看的群聊。
  const handleDeleteBatch = async (groupId: string, batchId: string) => {
    if (mutationLock.current) return false;
    mutationLock.current = true;
    setIncrementalBusy(true);
    setIncrementalMutationError("");
    try {
      const ok = await deleteIncrementalBatch(groupId, batchId);
      if (!mounted.current) return false;
      if (!ok) throw new Error("批次不存在或已被移除");
      toast.success(`已删除批次 ${batchId}`);
      if (currentGroup.current === groupId) await loadIncrementalData(groupId);
      return true;
    } catch (reason) {
      if (mounted.current)
        setIncrementalMutationError(
          reason instanceof Error ? `删除失败：${reason.message}` : "删除失败，请稍后重试。",
        );
      return false;
    } finally {
      mutationLock.current = false;
      if (mounted.current) setIncrementalBusy(false);
    }
  };

  const handleResetIncrGroup = async (groupId: string) => {
    if (mutationLock.current) return false;
    mutationLock.current = true;
    setIncrementalBusy(true);
    setIncrementalMutationError("");
    try {
      const res = await resetIncrementalGroup(groupId);
      if (!mounted.current) return false;
      toast.success(`已重置群 ${groupId}，清理了 ${res.deleted_batches} 个批次`);
      if (currentGroup.current === groupId) await loadIncrementalData(groupId);
      if (!mounted.current) return false;
      await refreshIncrGroups();
      return true;
    } catch (reason) {
      if (mounted.current)
        setIncrementalMutationError(
          reason instanceof Error ? `重置失败：${reason.message}` : "重置失败，请稍后重试。",
        );
      return false;
    } finally {
      mutationLock.current = false;
      if (mounted.current) setIncrementalBusy(false);
    }
  };

  // 刷新 Checkpoint 群列表与列表
  const refreshCheckpointGroups = useCallback(async () => {
    try {
      const groups = await fetchCheckpointGroups();
      setCkptGroups(groups);
    } catch {
      toast.error("获取 Checkpoint 群号列表失败");
    }
  }, []);

  const loadCheckpoints = useCallback(
    async (
      page = checkpointsPage,
      pageSize = checkpointsPageSize,
      group = ckptFilterGroup,
      date = ckptFilterDate,
      stage = ckptFilterStage,
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
        toast.error("加载阶段快照列表失败");
      } finally {
        setLoadingCheckpoints(false);
      }
    },
    [checkpointsPage, checkpointsPageSize, ckptFilterGroup, ckptFilterDate, ckptFilterStage],
  );

  // 查看 Checkpoint JSON 详情
  const handleOpenCkptDetail = async (item: CheckpointItem) => {
    setCkptDetailModalOpen(true);
    setSelectedCkptDetail({
      checkpoint_id: item.checkpoint_id,
      group_id: item.group_id,
      date_str: item.date_str,
      stage_name: item.stage_name,
      trace_id: item.trace_id,
      created_at: item.created_at,
      created_at_formatted: item.created_at_formatted,
      data_size_bytes: item.data_size_bytes ?? item.data_size,
      data: undefined,
    });
    setLoadingCkptDetail(true);
    try {
      const detail = await fetchCheckpointDetail(
        item.group_id,
        item.date_str,
        item.stage_name,
        item.trace_id,
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
          trace_id: detail.trace_id || item.trace_id,
          created_at: detail.created_at ?? item.created_at,
          created_at_formatted: detail.created_at_formatted || item.created_at_formatted,
          data_size_bytes: detail.data_size_bytes ?? detail.data_size ?? item.data_size_bytes,
          data: payloadData,
        });
      } else {
        toast.error("快照数据不存在或已过期");
      }
    } catch {
      toast.error("获取快照详情异常");
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
    stageName?: string,
    traceId?: string,
  ) => {
    try {
      const ok = await deleteCheckpoint(groupId, dateStr, stageName, traceId);
      if (ok) {
        toast.success(
          stageName
            ? `已删除 ${groupId} (${dateStr}) 的阶段快照「${stageName}」`
            : `已清空 ${groupId} (${dateStr}) 的所有阶段快照`,
        );
        await loadCheckpoints();
        await refreshCheckpointGroups();
      } else {
        toast.error("删除快照失败");
      }
    } catch {
      toast.error("删除快照异常");
    }
  };

  // 全局刷新
  const refreshAll = useCallback(async () => {
    await Promise.all([refreshIncrGroups(), refreshCheckpointGroups()]);
  }, [refreshIncrGroups, refreshCheckpointGroups]);

  return {
    // 2. 增量
    incrGroups,
    selectedIncrGroup,
    incrBatches,
    incrCursor,
    loadingIncremental,
    incrementalError,
    incrGroupsError,
    incrementalMutationError,
    incrementalBusy,
    clearIncrementalMutationError: () => setIncrementalMutationError(""),
    batchDetailModalOpen,
    selectedBatchDetail,
    loadingBatchDetail,
    batchDetailError,
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
