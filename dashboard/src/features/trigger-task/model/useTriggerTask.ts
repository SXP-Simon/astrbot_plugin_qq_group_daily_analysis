import { useState } from "react";
import { message } from "antd";
import { triggerNewTask } from "../../../entities/task/api/taskApi";

export function useTriggerTask(onSuccess?: () => void) {
  const [open, setOpen] = useState(false);
  const [groupId, setGroupId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [platform, setPlatform] = useState("qq");
  const [submitting, setSubmitting] = useState(false);

  const handleOpen = () => {
    setGroupId("");
    setGroupName("");
    setPlatform("qq");
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
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
    setGroupId,
    groupName,
    setGroupName,
    platform,
    setPlatform,
    submitting,
    handleOpen,
    handleClose,
    handleSubmit,
  };
}
