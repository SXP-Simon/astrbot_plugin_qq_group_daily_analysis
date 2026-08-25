import { useState } from "react";
import { message } from "antd";
import {
  triggerNewTask,
  fetchConnectedPlatforms,
  ConnectedPlatform,
} from "../../../entities/task/api/taskApi";
import { GroupItem } from "../../../entities/group/model/types";

export function useTriggerTask(groups: GroupItem[] = [], onSuccess?: () => void) {
  const [open, setOpen] = useState(false);
  const [groupId, setGroupId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [platform, setPlatform] = useState("auto");
  const [submitting, setSubmitting] = useState(false);
  const [connectedPlatforms, setConnectedPlatforms] = useState<ConnectedPlatform[]>([]);
  const [loadingPlatforms, setLoadingPlatforms] = useState(false);

  const loadPlatforms = async () => {
    try {
      setLoadingPlatforms(true);
      const list = await fetchConnectedPlatforms();
      setConnectedPlatforms(list);
    } catch {
      // Ignore background failure, fallback options will be displayed
    } finally {
      setLoadingPlatforms(false);
    }
  };

  const handleOpen = () => {
    setGroupId("");
    setGroupName("");
    setPlatform("auto");
    setOpen(true);
    loadPlatforms();
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
      const res = await triggerNewTask(trimmedId, groupName.trim(), platform);
      if (res.status === "ok") {
        message.success("分析任务已提交到执行队列");
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
    submitting,
    connectedPlatforms,
    loadingPlatforms,
    handleOpen,
    handleClose,
    handleSubmit,
  };
}
