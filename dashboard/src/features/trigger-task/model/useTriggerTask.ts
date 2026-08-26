import { useState } from "react";
import { message } from "antd";
import {
  triggerNewTask,
  fetchConnectedPlatforms,
  ConnectedPlatform,
} from "../../../entities/task/api/taskApi";
import {
  fetchProviderList,
  LLMProviderItem,
} from "../../../entities/trace/api/traceApi";
import { GroupItem } from "../../../entities/group/model/types";

export function useTriggerTask(groups: GroupItem[] = [], onSuccess?: () => void) {
  const [open, setOpen] = useState(false);
  const [groupId, setGroupId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [platform, setPlatform] = useState("auto");
  const [providerId, setProviderId] = useState("auto");
  const [submitting, setSubmitting] = useState(false);
  const [connectedPlatforms, setConnectedPlatforms] = useState<ConnectedPlatform[]>([]);
  const [loadingPlatforms, setLoadingPlatforms] = useState(false);
  const [providers, setProviders] = useState<LLMProviderItem[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);

  const loadOptions = async () => {
    try {
      setLoadingPlatforms(true);
      setLoadingProviders(true);
      const [platList, provList] = await Promise.allSettled([
        fetchConnectedPlatforms(),
        fetchProviderList(),
      ]);
      if (platList.status === "fulfilled") setConnectedPlatforms(platList.value);
      if (provList.status === "fulfilled") setProviders(provList.value);
    } catch {
      // Ignore background failure, fallback options will be displayed
    } finally {
      setLoadingPlatforms(false);
      setLoadingProviders(false);
    }
  };

  const handleOpen = () => {
    setGroupId("");
    setGroupName("");
    setPlatform("auto");
    setProviderId("auto");
    setOpen(true);
    loadOptions();
  };

  const handleClose = () => {
    setOpen(false);
  };

  const handleGroupIdChange = (val: string) => {
    setGroupId(val);
    const matched = groups.find((g) => g.group_id === val.trim());
    if (matched) {
      if (matched.group_name && !groupName) {
        setGroupName(matched.group_name);
      }
      if (matched.platform && platform === "auto") {
        setPlatform(matched.platform);
      }
    }
  };

  const handleSubmit = async () => {
    const trimmedId = groupId.trim();
    if (!trimmedId) {
      message.warning("请输入目标群号");
      return;
    }

    setSubmitting(true);
    try {
      const res = await triggerNewTask(
        trimmedId,
        groupName.trim(),
        platform,
        providerId !== "auto" ? providerId : undefined
      );
      if (res.status === "ok") {
        const traceInfo = res.trace_id ? ` (任务编号: ${res.trace_id})` : "";
        message.success(`分析任务已提交到执行队列${traceInfo}`);
        setOpen(false);
        if (onSuccess) onSuccess();
      } else {
        message.error(`触发失败: ${res.message || "未知错误"}`);
      }
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      message.error(`请求异常: ${errMsg}`);
    } finally {
      setSubmitting(false);
    }
  };

  return {
    open,
    groupId,
    setGroupId: handleGroupIdChange,
    groupName,
    setGroupName,
    platform,
    setPlatform,
    providerId,
    setProviderId,
    submitting,
    connectedPlatforms,
    loadingPlatforms,
    providers,
    loadingProviders,
    handleOpen,
    handleClose,
    handleSubmit,
  };
}
