import { useCallback, useEffect, useRef, useState } from "react";
import { message } from "antd";
import { fetchDistinctGroups } from "../../../entities/group/api/groupApi";
import type { GroupItem } from "../../../entities/group/model/types";
import { fetchComicRotationStatus, resetComicRotation } from "../api/comicRotationApi";
import { isComicGroupUmo, normalizeComicRotation, type ComicTemplateRotationStatus } from "./comicTemplateRotation";

interface ComicTemplateRotationProps {
  value: Record<string, unknown>;
  savedValue: Record<string, unknown>;
  dirty: boolean;
  disabled?: boolean;
  onPatch: (patch: Record<string, unknown>) => void;
}

/** 配置草稿与服务器进度分别维护，迟到的其他群状态不能覆盖当前群。 */
export function useComicTemplateRotation({ value, savedValue, dirty, disabled = false, onPatch }: ComicTemplateRotationProps) {
  const settings = normalizeComicRotation(value);
  const saved = normalizeComicRotation(savedValue);
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [groupError, setGroupError] = useState("");
  const [groupLoading, setGroupLoading] = useState(false);
  const [groupRevision, setGroupRevision] = useState(0);
  const [selectedUmo, setSelectedUmo] = useState("");
  const [manualUmo, setManualUmo] = useState("");
  const [manualError, setManualError] = useState("");
  const [status, setStatus] = useState<ComicTemplateRotationStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState("");
  const [resetting, setResetting] = useState(false);
  const [revision, setRevision] = useState(0);
  const requestId = useRef(0);
  const generation = useRef(0);
  const target = saved.scope === "group" ? selectedUmo : undefined;
  const savedKey = JSON.stringify(savedValue);
  const statusReady = saved.scope === "global" || isComicGroupUmo(selectedUmo);
  const refresh = useCallback(() => setRevision((previous) => previous + 1), []);

  useEffect(() => {
    if (saved.scope !== "group") return;
    let active = true;
    setGroupLoading(true);
    setGroupError("");
    void fetchDistinctGroups(groupRevision > 0).then((next) => { if (active) setGroups(next); })
      .catch((reason: unknown) => { if (active) setGroupError(reason instanceof Error ? reason.message : "群列表加载失败"); })
      .finally(() => { if (active) setGroupLoading(false); });
    return () => { active = false; };
  }, [saved.scope, groupRevision]);

  useEffect(() => {
    const current = ++requestId.current;
    ++generation.current;
    setStatus(null);
    setStatusError("");
    setStatusLoading(statusReady);
    if (!statusReady) return;
    let active = true;
    const timeout = window.setTimeout(() => {
      active = false;
      if (requestId.current === current) { setStatusError("读取切换状态超时，请重试"); setStatusLoading(false); }
    }, 15000);
    void fetchComicRotationStatus(target).then((next) => {
      if (active && requestId.current === current) setStatus(next);
    }).catch((reason: unknown) => {
      if (active && requestId.current === current) setStatusError(reason instanceof Error ? reason.message : "读取切换状态失败");
    }).finally(() => {
      window.clearTimeout(timeout);
      if (active && requestId.current === current) setStatusLoading(false);
    });
    return () => { active = false; window.clearTimeout(timeout); };
  }, [target, statusReady, savedKey, revision]);

  useEffect(() => () => { ++generation.current; }, []);

  const options = groups.filter(({ platform, group_id }) => !["auto", "default", "all"].includes(platform) && isComicGroupUmo(`${platform}:GroupMessage:${group_id}`))
    .map(({ platform, group_id, group_name }) => ({ value: `${platform}:GroupMessage:${group_id}`, label: `${group_name || group_id} · ${group_id} · ${platform}` }));
  if (selectedUmo && !options.some(({ value: id }) => id === selectedUmo)) options.push({ value: selectedUmo, label: selectedUmo });
  const selectManual = () => {
    const next = manualUmo.trim();
    if (!isComicGroupUmo(next)) { setManualError("请填写 /sid 返回的完整群会话标识，例如 bot:GroupMessage:123456。"); return; }
    setSelectedUmo(next);
    setManualUmo("");
    setManualError("");
  };
  const setCandidates = (candidates: string[]) => {
    if (disabled) return;
    // 新加入的模板追加在末尾，已有顺序不受多选控件展示次序影响。
    const selected = new Set(candidates);
    onPatch({ comic_template_candidates: [...settings.candidates.filter((id) => selected.has(id)), ...candidates.filter((id) => !settings.candidates.includes(id))] });
  };
  const moveCandidate = (id: string, step: -1 | 1) => {
    if (disabled) return;
    const next = [...settings.candidates];
    const index = next.indexOf(id);
    if (index < 0 || index + step < 0 || index + step >= next.length) return;
    [next[index], next[index + step]] = [next[index + step], next[index]];
    onPatch({ comic_template_candidates: next });
  };
  const resetLocked = disabled || dirty || resetting || statusLoading || Boolean(statusError) || !statusReady || saved.mode === "fixed" || !status;
  const reset = async () => {
    if (resetLocked) return;
    const current = generation.current;
    setResetting(true);
    setStatusError("");
    let timeout: number | undefined;
    try {
      const next = await Promise.race([
        resetComicRotation(target),
        new Promise<never>((_resolve, reject) => { timeout = window.setTimeout(() => reject(new Error("重置请求超时，结果尚未确认。请刷新进度核对后再操作。")), 15000); }),
      ]);
      if (current === generation.current) { setStatus(next); message.success("漫画模板切换进度已重置"); }
    } catch (reason: unknown) {
      if (current === generation.current) setStatusError(reason instanceof Error ? reason.message : "重置失败，请刷新状态核对");
    } finally { window.clearTimeout(timeout); setResetting(false); }
  };
  return { settings, saved, status, statusLoading, statusError, refreshing: statusLoading, refresh, resetting, resetLocked, reset, options, selectedUmo, setSelectedUmo, manualUmo, setManualUmo, manualError, selectManual, groupError, groupLoading, refreshGroups: () => setGroupRevision((previous) => previous + 1), setCandidates, moveCandidate };
}
