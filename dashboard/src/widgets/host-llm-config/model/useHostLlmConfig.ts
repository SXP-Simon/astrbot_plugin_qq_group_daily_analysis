import { useEffect, useMemo, useState } from "react";
import { fetchHostLlmConfig } from "@/entities/config/api/hostLlmApi";
import { describeLlmChains, type HostLlmConfig } from "@/entities/config/model/hostLlmConfig";
import { fetchGroupSessions } from "@/entities/group/api/groupApi";
import type { GroupItem } from "@/entities/group/model/types";

export function useHostLlmConfig(draft: Record<string, unknown>) {
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [groupError, setGroupError] = useState("");
  const [selection, setSelection] = useState("");
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{
    key: string;
    data: HostLlmConfig | null;
    error: string;
  }>();
  const key = `${selection}:${revision}`;
  const options = useMemo(
    () =>
      groups
        .filter((group) => group.platform)
        .map((group) => ({
          key: JSON.stringify([group.platform, group.group_id]),
          label: `${group.group_name || group.group_id} · ${group.group_id} · ${group.platform}`,
          group,
        })),
    [groups],
  );
  const selected = options.find((option) => option.key === selection)?.group;

  useEffect(() => {
    let active = true;
    void fetchGroupSessions()
      .then((items) => {
        if (active) {
          setGroups(items);
          setGroupError("");
        }
      })
      .catch(() => {
        if (active) setGroupError("群会话列表暂时无法读取，仍可查看宿主默认配置。");
      });
    return () => {
      active = false;
    };
  }, [revision]);

  useEffect(() => {
    let active = true;
    if (selection && !selected) {
      setResult({ key, data: null, error: "所选会话已不在列表中，请重新选择查看范围。" });
      return () => {
        active = false;
      };
    }
    void fetchHostLlmConfig(selected)
      .then((data) => {
        if (active) setResult({ key, data, error: "" });
      })
      .catch(() => {
        if (active) setResult({ key, data: null, error: "宿主模型信息读取失败，请刷新重试。" });
      });
    return () => {
      active = false;
    };
  }, [key, selected, selection]);

  // 选择变化后隐藏旧会话结果，迟到响应也不能覆盖当前选择。
  const current = result?.key === key ? result : undefined;
  return {
    options,
    selection,
    setSelection,
    groupError,
    loading: !current,
    error: current?.error,
    data: current?.data,
    chains: current?.data ? describeLlmChains(current.data, draft) : null,
    refresh: () => setRevision((value) => value + 1),
  };
}
