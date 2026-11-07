import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  fetchCheckpointGroups,
  fetchCheckpointsList,
  fetchCheckpointDetail,
  deleteCheckpoint,
} from "../../../entities/plugin-data/api/pluginDataApi";
import type { CheckpointItem, CheckpointDetail } from "../../../entities/plugin-data/model/types";

interface CheckpointQuery {
  page: number;
  pageSize: number;
  group?: string;
  date?: string;
  stage?: string;
}

export function useCheckpointsViewModel() {
  const [query, setQuery] = useState<CheckpointQuery>({ page: 1, pageSize: 20 });
  const queryRef = useRef(query);
  const listRequest = useRef(0);
  const detailRequest = useRef(0);
  const groupRequest = useRef(0);
  const deleting = useRef(false);
  const mounted = useRef(true);
  const [ckptGroups, setGroups] = useState<string[]>([]);
  const [checkpointGroupsError, setGroupsError] = useState("");
  const [checkpoints, setItems] = useState<CheckpointItem[]>([]);
  const [checkpointsTotal, setTotal] = useState(0);
  const [loadingCheckpoints, setLoading] = useState(false);
  const [checkpointError, setError] = useState("");
  const [ckptDetailModalOpen, setDetailOpen] = useState(false);
  const [selectedCkptDetail, setDetail] = useState<CheckpointDetail | null>(null);
  const [loadingCkptDetail, setDetailLoading] = useState(false);
  const [checkpointDetailError, setDetailError] = useState("");
  const [checkpointDeleting, setDeleting] = useState(false);
  const [checkpointDeleteError, setDeleteError] = useState("");
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      listRequest.current += 1;
      detailRequest.current += 1;
      groupRequest.current += 1;
    };
  }, []);
  const refreshCheckpointGroups = useCallback(async () => {
    if (!mounted.current) return;
    const request = ++groupRequest.current;
    setGroupsError("");
    try {
      const groups = await fetchCheckpointGroups();
      if (request === groupRequest.current) setGroups(groups);
    } catch {
      if (request === groupRequest.current) setGroupsError("群聊列表读取失败，可刷新重试。");
    }
  }, []);

  const loadCheckpoints = useCallback(async (changes: Partial<CheckpointQuery> = {}) => {
    if (!mounted.current) return;
    const next = { ...queryRef.current, ...changes };
    next.page = Number.isFinite(next.page) ? Math.max(1, Math.floor(next.page)) : 1;
    next.pageSize = [10, 20, 50, 100].includes(next.pageSize) ? next.pageSize : 20;
    const changed = Object.entries(next).some(
      ([key, value]) => queryRef.current[key as keyof CheckpointQuery] !== value,
    );
    queryRef.current = next;
    setQuery(next);
    const request = ++listRequest.current;
    setLoading(true);
    setError("");
    if (changed) {
      setItems([]);
      setTotal(0);
    }
    try {
      let result = await fetchCheckpointsList({
        limit: next.pageSize,
        offset: (next.page - 1) * next.pageSize,
        group_id: next.group,
        date_str: next.date,
        stage_name: next.stage,
      });
      if (request !== listRequest.current) return;
      const lastPage = Math.max(1, Math.ceil(result.total / next.pageSize));
      if (next.page > lastPage) {
        const corrected = { ...next, page: lastPage };
        queryRef.current = corrected;
        setQuery(corrected);
        result = await fetchCheckpointsList({
          limit: next.pageSize,
          offset: (lastPage - 1) * next.pageSize,
          group_id: next.group,
          date_str: next.date,
          stage_name: next.stage,
        });
        if (request !== listRequest.current) return;
      }
      setItems(result.items);
      setTotal(result.total);
    } catch (cause) {
      if (request === listRequest.current)
        setError(
          cause instanceof Error ? `快照读取失败：${cause.message}` : "快照读取失败，请刷新重试。",
        );
    } finally {
      if (request === listRequest.current) setLoading(false);
    }
  }, []);

  const handleOpenCkptDetail = async (item: CheckpointItem) => {
    const request = ++detailRequest.current;
    setDetailOpen(true);
    setDetail({ ...item, data: undefined });
    setDetailLoading(true);
    setDetailError("");
    try {
      const detail = await fetchCheckpointDetail(
        item.group_id,
        item.date_str,
        item.stage_name,
        item.trace_id,
      );
      if (request !== detailRequest.current) return;
      if (!detail) throw new Error("快照已不存在或已过期，请刷新列表。");
      if (
        detail.group_id !== item.group_id ||
        detail.date_str !== item.date_str ||
        detail.stage_name !== item.stage_name ||
        (detail.trace_id || "") !== (item.trace_id || "")
      )
        throw new Error("返回的快照与所选记录不一致，请重新读取。");
      setDetail({
        ...item,
        ...detail,
        data: detail.checkpoint_data !== undefined ? detail.checkpoint_data : detail.data,
      });
    } catch (cause) {
      if (request === detailRequest.current)
        setDetailError(cause instanceof Error ? cause.message : "快照详情读取失败，请重试。");
    } finally {
      if (request === detailRequest.current) setDetailLoading(false);
    }
  };
  const handleCloseCkptDetail = () => {
    detailRequest.current += 1;
    setDetailOpen(false);
    setDetail(null);
    setDetailLoading(false);
    setDetailError("");
  };
  const handleDeleteCheckpoint = async (
    groupId: string,
    dateStr: string,
    stageName?: string,
    traceId?: string,
  ) => {
    if (deleting.current) return false;
    deleting.current = true;
    setDeleting(true);
    setDeleteError("");
    const request = listRequest.current;
    try {
      const ok = await deleteCheckpoint(groupId, dateStr, stageName, traceId);
      if (!mounted.current) return false;
      if (!ok) throw new Error("快照不存在或已被删除。");
      toast.success("已删除阶段快照");
      if (request === listRequest.current) await loadCheckpoints();
      if (mounted.current) await refreshCheckpointGroups();
      return true;
    } catch (cause) {
      if (mounted.current)
        setDeleteError(cause instanceof Error ? cause.message : "删除失败，请稍后重试。");
      return false;
    } finally {
      deleting.current = false;
      if (mounted.current) setDeleting(false);
    }
  };
  return {
    ckptGroups,
    checkpointGroupsError,
    checkpoints,
    checkpointsTotal,
    checkpointsPage: query.page,
    checkpointsPageSize: query.pageSize,
    ckptFilterGroup: query.group,
    ckptFilterDate: query.date,
    ckptFilterStage: query.stage,
    loadingCheckpoints,
    checkpointError,
    ckptDetailModalOpen,
    selectedCkptDetail,
    loadingCkptDetail,
    checkpointDetailError,
    checkpointDeleting,
    checkpointDeleteError,
    clearCheckpointDeleteError: () => setDeleteError(""),
    refreshCheckpointGroups,
    loadCheckpoints,
    handleOpenCkptDetail,
    handleCloseCkptDetail,
    handleDeleteCheckpoint,
  };
}
