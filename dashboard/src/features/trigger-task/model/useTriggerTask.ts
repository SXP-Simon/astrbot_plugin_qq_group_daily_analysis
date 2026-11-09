import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  triggerNewTask,
  fetchConnectedPlatforms,
  type ConnectedPlatform,
} from "@/entities/task/api/taskApi";
import { fetchProviderList, type LLMProviderItem } from "@/entities/trace/api/traceApi";
import { useReportTemplates } from "@/entities/report/model/useReportTemplates";
import type { GroupItem } from "@/entities/group/model/types";

export function useTriggerTask(groups: GroupItem[] = [], onSuccess?: () => void) {
  const [open, setOpen] = useState(false);
  const [groupId, setGroupId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [platform, setPlatform] = useState("auto");
  const [providerId, setProviderId] = useState("auto");
  const [templateName, setTemplateName] = useState("auto");
  const [submitting, setSubmitting] = useState(false);
  const [connectedPlatforms, setConnectedPlatforms] = useState<ConnectedPlatform[]>([]);
  const [providers, setProviders] = useState<LLMProviderItem[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [optionsError, setOptionsError] = useState("");
  const [optionsVersion, setOptionsVersion] = useState(0);
  const pending = useRef(false);
  const mounted = useRef(false);
  const inferred = useRef({ name: "", platform: "" });
  const {
    templates,
    loading: loadingTemplates,
    ready,
    error: templatesError,
    refresh: refreshTemplates,
  } = useReportTemplates("configured", open);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoadingOptions(true);
    setOptionsError("");
    void Promise.allSettled([fetchConnectedPlatforms(), fetchProviderList()]).then(
      ([platforms, models]) => {
        if (!active) return;
        setConnectedPlatforms(platforms.status === "fulfilled" ? platforms.value : []);
        setProviders(models.status === "fulfilled" ? models.value : []);
        const failures = [
          platforms.status === "rejected" ? "平台" : "",
          models.status === "rejected" ? "模型" : "",
        ].filter(Boolean);
        setOptionsError(
          failures.length ? `${failures.join("和")}列表未能读取，可重试加载或使用默认选择。` : "",
        );
        setLoadingOptions(false);
      },
    );
    return () => {
      active = false;
    };
  }, [open, optionsVersion]);

  const handleOpen = () => {
    if (pending.current) return;
    setGroupId("");
    setGroupName("");
    setPlatform("auto");
    setProviderId("auto");
    setTemplateName("auto");
    inferred.current = { name: "", platform: "" };
    setOpen(true);
  };
  const handleGroupIdChange = (value: string) => {
    setGroupId(value);
    const inferPlatform = platform === "auto" || platform === inferred.current.platform;
    const platformType = connectedPlatforms.find((item) => item.id === platform)?.type ?? platform;
    const matches = groups.filter(
      (group) =>
        group.group_id === value.trim() &&
        (inferPlatform || group.platform === platform || group.platform === platformType),
    );
    // 不同平台可能存在相同群号；只有唯一匹配时才补全名称或平台。
    const match = matches.length === 1 ? matches[0] : undefined;
    if (!groupName || groupName === inferred.current.name) {
      const name = match?.group_name ?? "";
      setGroupName(name);
      inferred.current.name = name;
    }
    if (inferPlatform) {
      const instances = connectedPlatforms.filter(
        (item) => item.id === match?.platform || item.type === match?.platform,
      );
      const next =
        instances.length === 1
          ? instances[0].id
          : connectedPlatforms.length === 0
            ? match?.platform || "auto"
            : "auto";
      setPlatform(next);
      inferred.current.platform = next;
    }
  };
  const handleSubmit = async () => {
    if (pending.current || !open) return;
    const id = groupId.trim();
    if (!id) throw new Error("请输入群聊或会话标识。");
    if (templateName !== "auto" && (!ready || !templates.some((item) => item.id === templateName)))
      throw new Error(templatesError || "所选模板当前不可用，请重新选择。");
    pending.current = true;
    setSubmitting(true);
    try {
      const response = await triggerNewTask(
        id,
        groupName.trim(),
        platform,
        providerId === "auto" ? undefined : providerId,
        templateName === "auto" ? undefined : templateName,
      );
      if (response.status !== "ok")
        throw new Error(response.message || "未能发起分析，请稍后重试。");
      if (!mounted.current) return;
      setOpen(false);
      toast.success("分析任务已提交", {
        description: response.trace_id ? `任务编号：${response.trace_id}` : undefined,
      });
      try {
        onSuccess?.();
      } catch {
        toast.warning("任务已提交，列表未能更新。请手动刷新查看。");
      }
    } finally {
      pending.current = false;
      if (mounted.current) setSubmitting(false);
    }
  };
  return {
    open,
    groupId,
    setGroupId: handleGroupIdChange,
    groupName,
    setGroupName: (value: string) => {
      inferred.current.name = "";
      setGroupName(value);
    },
    platform,
    setPlatform: (value: string) => {
      inferred.current.platform = "";
      setPlatform(value);
    },
    providerId,
    setProviderId,
    templateName,
    setTemplateName,
    submitting,
    connectedPlatforms,
    loadingPlatforms: open && loadingOptions,
    providers,
    loadingProviders: open && loadingOptions,
    optionsError,
    refreshOptions: () => setOptionsVersion((version) => version + 1),
    templates,
    loadingTemplates,
    templatesError,
    refreshTemplates,
    handleOpen,
    handleClose: () => {
      if (!pending.current) setOpen(false);
    },
    handleSubmit,
  };
}
