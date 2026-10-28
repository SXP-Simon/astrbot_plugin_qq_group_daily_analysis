import { useEffect, useRef, useState } from "react";
import { testT2i } from "../../../entities/config/api/configApi";
import type { T2iProbe, T2iProbeInput } from "../../../entities/config/model/t2iProbe";
import { fetchDistinctGroups } from "../../../entities/group/api/groupApi";
import type { GroupItem } from "../../../entities/group/model/types";

export function useT2iProbe(input: T2iProbeInput) {
  const sequence = useRef(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<T2iProbe | null>(null);
  const [error, setError] = useState("");
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [groupKey, setGroupKey] = useState("");
  const [groupsError, setGroupsError] = useState("");
  const hostService = input.render_service === "astrbot";
  const selectedGroup = groups.find((group) => JSON.stringify([group.platform, group.group_id]) === groupKey);

  useEffect(() => {
    if (!hostService) return;
    let active = true;
    void fetchDistinctGroups().then((list) => {
      if (active) { setGroups(list.filter((group) => Boolean(group.platform))); setGroupsError(""); }
    }).catch(() => {
      if (active) setGroupsError("群列表暂时无法读取，可以先测试 AstrBot 默认配置。");
    });
    return () => { active = false; };
  }, [hostService]);

  useEffect(() => {
    sequence.current += 1;
    setLoading(false);
    setResult(null);
    setError("");
    return () => { sequence.current += 1; };
  }, [input.render_service, input.service_endpoint, input.service_token, input.timeout, input.request_timeout, input.group_id, input.platform_id, groupKey]);

  const run = async () => {
    if (loading) return;
    const requestId = ++sequence.current;
    setLoading(true);
    setResult(null);
    setError("");
    try {
      const data = await testT2i(hostService && selectedGroup ? {
        ...input, group_id: selectedGroup.group_id, platform_id: selectedGroup.platform,
      } : input);
      if (sequence.current === requestId) setResult(data);
    } catch (err: unknown) {
      if (sequence.current === requestId) setError(err instanceof Error ? err.message : "测试没能完成，请稍后再试。");
    } finally {
      if (sequence.current === requestId) setLoading(false);
    }
  };

  const groupOptions = [
    { value: "", label: "AstrBot 默认配置" },
    ...groups.map((group) => ({
      value: JSON.stringify([group.platform, group.group_id]),
      label: `${group.group_name || group.group_id}（${group.group_id} · ${group.platform}）`,
    })),
  ];
  return { loading, result, error, run, groupOptions, groupKey, setGroupKey, groupsError };
}
