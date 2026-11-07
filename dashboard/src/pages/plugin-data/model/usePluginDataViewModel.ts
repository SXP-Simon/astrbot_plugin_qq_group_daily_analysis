import { useState, useCallback, useRef, useEffect } from "react";
import { toast } from "sonner";
import {
  fetchIncrementalGroupDirectory,
  fetchIncrementalBatches,
  fetchIncrementalBatchDetail,
  deleteIncrementalBatch,
  resetIncrementalGroup,
  IncrementalBatchItem,
  IncrementalCursorInfo,
  IncrementalGroupDirectoryItem,
} from "../../../entities/plugin-data/api/pluginDataApi";

import { useCheckpointsViewModel } from "./useCheckpointsViewModel";

export function usePluginDataViewModel() {
  const checkpointVM = useCheckpointsViewModel();
  const { refreshCheckpointGroups } = checkpointVM;
  // 2. 增量分析批次管理
  const [incrGroupDetails, setIncrGroupDetails] = useState<IncrementalGroupDirectoryItem[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<IncrementalGroupDirectoryItem | null>(null);
  const selectedIncrGroup = selectedTarget?.group_id || "";
  const selectedIncrPlatform = selectedTarget?.platform_id || "";
  const [incrBatches, setIncrBatches] = useState<IncrementalBatchItem[]>([]);
  const [incrPagination, setIncrPagination] = useState({ page: 1, pageSize: 20, total: 0 });
  const incrementalQuery = useRef({ page: 1, pageSize: 20 });
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
  const currentPlatform = useRef("");
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

  // 刷新增量群列表
  const refreshIncrGroups = useCallback(async () => {
    const request = ++groupsRequest.current;
    setIncrGroupsError("");
    try {
      const directory = await fetchIncrementalGroupDirectory();
      if (request !== groupsRequest.current) return;
      setIncrGroupDetails(directory.group_details);
      setSelectedTarget(
        (current) =>
          directory.group_details.find(
            (target) =>
              target.group_id === current?.group_id && target.platform_id === current?.platform_id,
          ) ||
          directory.group_details[0] ||
          null,
      );
    } catch {
      if (request === groupsRequest.current) setIncrGroupsError("群聊列表读取失败，请刷新重试。");
    }
  }, []);

  // 切群和卸载立即废弃旧请求，同群刷新失败时保留上次记录。
  const loadIncrementalData = useCallback(
    async (
      groupId: string,
      page = incrementalQuery.current.page,
      pageSize = incrementalQuery.current.pageSize,
      platformId = currentPlatform.current,
    ) => {
      if (!groupId || currentGroup.current !== groupId || currentPlatform.current !== platformId)
        return;
      incrementalQuery.current = { page, pageSize };
      const request = ++incrementalRequest.current;
      setLoadingIncremental(true);
      setIncrementalError("");
      try {
        const res = await fetchIncrementalBatches(groupId, page, pageSize, platformId);
        if (
          request !== incrementalRequest.current ||
          currentGroup.current !== groupId ||
          currentPlatform.current !== platformId
        )
          return;
        if (
          res &&
          (res.group_id !== groupId ||
            (res.platform_id !== undefined && res.platform_id !== platformId) ||
            res.cursor.group_id !== groupId ||
            res.batches.some((batch) => batch.group_id !== groupId))
        )
          throw new Error("批次群聊不一致");
        incrementalQuery.current = { page: res?.page ?? 1, pageSize: res?.page_size ?? pageSize };
        setIncrPagination({ ...incrementalQuery.current, total: res?.total ?? 0 });
        setIncrBatches(res?.batches ?? []);
        setIncrCursor(res?.cursor ?? null);
      } catch {
        if (request === incrementalRequest.current)
          setIncrementalError("增量批次读取失败，请刷新重试；已有记录保持不变。");
      } finally {
        if (request === incrementalRequest.current) setLoadingIncremental(false);
      }
    },
    [],
  );

  useEffect(() => {
    currentGroup.current = selectedIncrGroup;
    currentPlatform.current = selectedIncrPlatform;
    batchDetailRequest.current += 1;
    setBatchDetailModalOpen(false);
    setSelectedBatchDetail(null);
    incrementalRequest.current += 1;
    incrementalQuery.current = { page: 1, pageSize: incrementalQuery.current.pageSize };
    setIncrPagination({ ...incrementalQuery.current, total: 0 });
    setIncrBatches([]);
    setIncrCursor(null);
    setIncrementalError("");
    setLoadingIncremental(false);
    if (selectedIncrGroup) void loadIncrementalData(selectedIncrGroup);
  }, [selectedIncrGroup, selectedIncrPlatform, loadIncrementalData]);

  const handleSelectIncrGroup = (groupId: string, platformId = currentPlatform.current) => {
    const target = incrGroupDetails.find(
      (item) => item.group_id === groupId && item.platform_id === platformId,
    );
    if (!target) return;
    currentGroup.current = groupId;
    currentPlatform.current = platformId;
    incrementalRequest.current += 1;
    batchDetailRequest.current += 1;
    setSelectedTarget(target);
  };

  // 请求编号同时隔离切换、关闭与卸载后的迟到响应。
  const handleOpenBatchDetail = async (item: IncrementalBatchItem) => {
    const request = ++batchDetailRequest.current;
    const platformId = currentPlatform.current;
    setBatchDetailModalOpen(true);
    setSelectedBatchDetail(item);
    setLoadingBatchDetail(true);
    setBatchDetailError("");
    try {
      const full = await fetchIncrementalBatchDetail(item.group_id, item.batch_id, platformId);
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
  const handleDeleteBatch = async (groupId: string, batchId: string, platformId: string) => {
    if (mutationLock.current) return false;
    mutationLock.current = true;
    setIncrementalBusy(true);
    setIncrementalMutationError("");
    try {
      const ok = await deleteIncrementalBatch(groupId, batchId, platformId);
      if (!mounted.current) return false;
      if (!ok) throw new Error("批次不存在或已被移除");
      toast.success(`已删除批次 ${batchId}`);
      if (currentGroup.current === groupId && currentPlatform.current === platformId)
        await loadIncrementalData(groupId, undefined, undefined, platformId);
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

  const handleResetIncrGroup = async (groupId: string, platformId: string) => {
    if (mutationLock.current) return false;
    mutationLock.current = true;
    setIncrementalBusy(true);
    setIncrementalMutationError("");
    try {
      const res = await resetIncrementalGroup(groupId, platformId);
      if (!mounted.current) return false;
      toast.success(`已重置群 ${groupId}，清理了 ${res.deleted_batches} 个批次`);
      if (currentGroup.current === groupId && currentPlatform.current === platformId)
        await loadIncrementalData(groupId, undefined, undefined, platformId);
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

  // 全局刷新
  const refreshAll = useCallback(async () => {
    await Promise.all([refreshIncrGroups(), refreshCheckpointGroups()]);
  }, [refreshIncrGroups, refreshCheckpointGroups]);

  return {
    // 2. 增量
    incrGroups: incrGroupDetails.map((item) => item.group_id),
    incrGroupOptions: incrGroupDetails.map((item) => ({
      value: JSON.stringify([item.platform_id, item.group_id]),
      label: `${item.group_name || "群名未记录"}（${item.group_id}） · ${item.platform_id || "平台未记录"}`,
    })),
    selectedIncrGroup,
    selectedIncrPlatform,
    selectedIncrSessionKey: selectedTarget
      ? JSON.stringify([selectedIncrPlatform, selectedIncrGroup])
      : "",
    handleSelectIncrSession: (key: string) => {
      const target = incrGroupDetails.find(
        (item) => JSON.stringify([item.platform_id, item.group_id]) === key,
      );
      if (target) handleSelectIncrGroup(target.group_id, target.platform_id);
    },
    incrBatches,
    incrCursor,
    incrPagination,
    changeIncrementalPage: (page: number, pageSize: number) =>
      loadIncrementalData(currentGroup.current, page, pageSize),
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

    ...checkpointVM,

    // 总刷新
    refreshAll,
  };
}
