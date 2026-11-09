import { renderingRuntimeSchema } from "@/entities/config/model/renderingConfig";
import { pluginConfigSaveSchema } from "@/entities/config/model/configContract";
import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { toast } from "sonner";
import {
  fetchPluginConfig,
  fetchAvailableProviders,
  fetchAvailablePersonas,
  savePluginConfig,
  AvailableProvider,
  AvailablePersona,
} from "@/entities/config/api/configApi";
import { PluginSchema } from "@/entities/config/model/types";
import { validateConfigWithZod, validateFieldIssues } from "@/entities/config/model/validation";

import { isFieldVisible } from "@/entities/config/model/visibility";
export { isFieldVisible, resolveDependencyValue } from "@/entities/config/model/visibility";

export function useConfigViewModel(onConfigSaved?: () => void | Promise<void>) {
  const [loading, setLoading] = useState(false);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [revision, setRevision] = useState<string>();
  const [saving, setSaving] = useState(false);
  const [schema, setSchema] = useState<PluginSchema>({});
  const [originalConfig, setOriginalConfig] = useState<Record<string, Record<string, unknown>>>({});
  const [formData, setFormData] = useState<Record<string, Record<string, unknown>>>({});
  const [providers, setProviders] = useState<AvailableProvider[]>([]);
  const [personas, setPersonas] = useState<AvailablePersona[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("basic");
  const [searchQuery, setSearchQuery] = useState("");
  const [loadError, setLoadError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [optionsError, setOptionsError] = useState("");
  const loadRequest = useRef(0);
  const lifecycle = useRef(0);
  const loadingRef = useRef(false);
  const savingRef = useRef(false);
  const focusTimer = useRef<ReturnType<typeof setTimeout>>();

  // 按分组和字段路径保存错误，列表下标区分同名字段。
  const [errors, setErrors] = useState<Record<string, Record<string, string>>>({});
  const groupErrorCounts = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(errors).map(([group, fields]) => [group, Object.keys(fields).length]),
      ),
    [errors],
  );

  const loadConfig = useCallback(async (isManual = false) => {
    if (savingRef.current) return false;
    const request = ++loadRequest.current;
    loadingRef.current = true;
    setLoading(true);
    setConfigLoaded(false);
    setLoadError("");
    setSaveError("");
    if (focusTimer.current) clearTimeout(focusTimer.current);
    try {
      const [configData, providerList, personaList] = await Promise.allSettled([
        fetchPluginConfig(),
        fetchAvailableProviders(),
        fetchAvailablePersonas(),
      ]);
      if (request !== loadRequest.current) return false;

      if (providerList.status === "fulfilled") {
        setProviders(providerList.value || []);
      }

      if (personaList.status === "fulfilled") {
        setPersonas(personaList.value || []);
      }
      const missing = [
        providerList.status === "rejected" ? "模型" : "",
        personaList.status === "rejected" ? "人格" : "",
      ].filter(Boolean);
      setOptionsError(
        missing.length
          ? `${missing.join("和")}选项暂时无法读取，已有填写值会保留，可重新读取后再选择。`
          : "",
      );

      if (configData.status === "rejected") throw configData.reason;
      if (configData.status === "fulfilled") {
        setConfigLoaded(true);
        const data = configData.value;
        setRevision(data.revision);
        setSchema(data.schema || {});
        setOriginalConfig(data.config || {});
        // 深拷贝一份 formData
        setFormData(structuredClone(data.config));

        const validation = validateConfigWithZod(data.config, data.schema, data.config);
        setErrors(validation.errorMap);
        const keys = Object.keys(data.schema);
        setActiveCategory((current) => (keys.includes(current) ? current : (keys[0] ?? "basic")));
        if (isManual) {
          toast.success("已重新读取最新配置");
        }
        return true;
      }
    } catch (error: unknown) {
      if (request !== loadRequest.current) return false;
      const reason =
        error instanceof Error ? error.message : "读取配置信息失败，请检查网络或后端状态";
      setLoadError(reason);
      toast.error(reason);
    } finally {
      if (request === loadRequest.current) {
        loadingRef.current = false;
        setLoading(false);
      }
    }
    return false;
  }, []);

  useEffect(() => {
    void loadConfig();
    const request = loadRequest;
    const epoch = lifecycle;
    const timer = focusTimer;
    return () => {
      request.current++;
      epoch.current++;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [loadConfig]);

  const handleFieldChange = (groupKey: string, fieldKey: string, value: unknown) => {
    if (loadingRef.current || !configLoaded) return;
    setFormData((prev) => {
      const next = { ...prev };
      if (!next[groupKey]) {
        next[groupKey] = {};
      }
      next[groupKey] = {
        ...next[groupKey],
        [fieldKey]: value,
      };
      return next;
    });

    // 实时校验当前字段，即时清除或更新错误提示
    const fieldSchema = schema[groupKey]?.items[fieldKey];
    if (fieldSchema) {
      const fieldErrors = validateFieldIssues(
        fieldKey,
        fieldSchema,
        value,
        originalConfig[groupKey]?.[fieldKey],
      );
      setErrors((prevErrors) => ({
        ...prevErrors,
        [groupKey]: {
          ...Object.fromEntries(
            Object.entries(prevErrors[groupKey] ?? {}).filter(
              ([path]) => path !== fieldKey && !path.startsWith(`${fieldKey}.`),
            ),
          ),
          ...fieldErrors,
        },
      }));
    }
  };

  const isDirty = useMemo(() => {
    return JSON.stringify(formData) !== JSON.stringify(originalConfig);
  }, [formData, originalConfig]);

  // 沿用侧栏一级配置项的计数口径，列表内部多处修改只计为一个配置项。
  const modifiedFields = useMemo(() => {
    const result: Record<string, ReadonlySet<string>> = {};
    for (const group of new Set([...Object.keys(originalConfig), ...Object.keys(formData)])) {
      const original = originalConfig[group] ?? {};
      const current = formData[group] ?? {};
      result[group] = new Set(
        [...new Set([...Object.keys(original), ...Object.keys(current)])].filter(
          (field) => JSON.stringify(original[field]) !== JSON.stringify(current[field]),
        ),
      );
    }
    return result;
  }, [formData, originalConfig]);

  const handleSave = async () => {
    if (savingRef.current) return;
    if (!configLoaded || loadingRef.current) {
      setSaveError("请等待配置成功加载后再保存");
      toast.error("请等待配置成功加载后再保存");
      return;
    }
    setSaveError("");
    if (focusTimer.current) clearTimeout(focusTimer.current);
    // 1. 保存前使用 Zod 执行严格校验
    const validationResult = validateConfigWithZod(formData, schema, originalConfig);

    if (!validationResult.isValid) {
      setErrors(validationResult.errorMap);

      const firstError = validationResult.errors[0];
      if (firstError) {
        // 自动切换到存在错误的分组 Tab
        setActiveCategory(firstError.groupKey);
        setSearchQuery("");

        // 无独立控件的错误定位到最近的可见条目。
        focusTimer.current = setTimeout(() => {
          const fields = Array.from(document.querySelectorAll<HTMLElement>("[data-config-path]"));
          let path = firstError.path;
          let targetDom: HTMLElement | undefined;
          while (path && !targetDom) {
            targetDom = fields.find((field) => field.dataset.configPath === path);
            path = path.slice(0, Math.max(0, path.lastIndexOf(".")));
          }

          if (!targetDom) {
            setSaveError(firstError.message);
            return;
          }
          if (targetDom.getClientRects().length > 0) {
            targetDom.scrollIntoView({
              behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
                ? "auto"
                : "smooth",
              block: "center",
            });
            const focusable =
              targetDom.querySelector<HTMLElement>(":scope > [role=alert][tabindex='-1']") ??
              targetDom.querySelector<HTMLElement>("input:not([type=hidden]), select, textarea") ??
              targetDom.querySelector<HTMLElement>("button:not(:disabled)");
            if (focusable) {
              focusable.focus({ preventScroll: true });
            }
          }
        }, 120);
      }
      return;
    }

    // 校验通过，清理错误状态
    setErrors({});

    // 2. 提交保存
    setSaving(true);
    savingRef.current = true;
    const epoch = lifecycle.current;
    try {
      const parsed = pluginConfigSaveSchema.safeParse(formData);
      if (!parsed.success) {
        setSaveError(parsed.error.issues[0].message);
        toast.error(parsed.error.issues[0].message);
        return;
      }
      const normalized = parsed.data;
      const res = revision
        ? await savePluginConfig(normalized, revision)
        : await savePluginConfig(normalized);
      if (epoch !== lifecycle.current) return;
      if (res.success) {
        setRevision(res.revision ?? revision);
        toast.success(res.message || "配置已成功保存并生效");
        setOriginalConfig(normalized);
        setFormData((current) => (current === formData ? normalized : current));
        try {
          await onConfigSaved?.();
        } catch {
          if (epoch === lifecycle.current)
            toast.warning("配置已保存，但相关页面未能刷新，请手动刷新查看。");
        }
      } else {
        setSaveError(res.message || "保存配置失败");
        toast.error(res.message || "保存配置失败");
      }
    } catch (error: unknown) {
      if (epoch !== lifecycle.current) return;
      const reason = error instanceof Error ? error.message : "保存配置请求发生异常";
      setSaveError(reason);
      toast.error(reason);
    } finally {
      if (epoch === lifecycle.current) {
        savingRef.current = false;
        setSaving(false);
      }
    }
  };

  // 分组列表元数据（支持搜索过滤高亮与计数）
  const categories = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return Object.entries(schema).map(([key, group]) => {
      const groupDesc = group.description || key;
      const items = group.items || {};

      const visibleItems = Object.entries(items).filter(
        ([fieldKey, item]) =>
          isFieldVisible(item, formData) &&
          (fieldKey !== "comic_style_scope" ||
            (formData.daily_comic?.comic_style_mode ?? "fixed") !== "fixed"),
      );

      let matchCount = 0;
      if (q) {
        if (
          key.toLowerCase().includes(q) ||
          groupDesc.toLowerCase().includes(q) ||
          (group.hint && group.hint.toLowerCase().includes(q))
        ) {
          matchCount += visibleItems.length;
        } else {
          for (const [fieldKey, item] of visibleItems) {
            const desc = (item.description || "").toLowerCase();
            const hint = (item.hint || "").toLowerCase();
            if (fieldKey.toLowerCase().includes(q) || desc.includes(q) || hint.includes(q)) {
              matchCount++;
            }
          }
        }
      }

      return {
        key,
        label: groupDesc,
        hint: group.hint || "",
        totalFields: visibleItems.length,
        matchCount: q ? matchCount : undefined,
      };
    });
  }, [schema, searchQuery, formData]);

  const matchingCategories = categories.filter(
    (category) => category.matchCount === undefined || category.matchCount > 0,
  );
  const displayedCategory = matchingCategories.some((category) => category.key === activeCategory)
    ? activeCategory
    : (matchingCategories[0]?.key ?? activeCategory);

  // 当前激活分组的字段列表（应用搜索过滤，并过滤 invisible 与 condition 条件隐藏项）
  const currentGroupFields = useMemo(() => {
    if (!schema[displayedCategory]) return [];
    const q = searchQuery.trim().toLowerCase();
    const group = schema[displayedCategory];
    const groupItems = group.items || {};
    const groupMatches =
      displayedCategory.toLowerCase().includes(q) ||
      group.description.toLowerCase().includes(q) ||
      (group.hint ?? "").toLowerCase().includes(q);

    return Object.entries(groupItems)
      .filter(([fieldKey, item]) => {
        // 过滤 schema 中声明为不可见或当前不满足 condition 的字段
        if (!isFieldVisible(item, formData)) return false;
        if (
          fieldKey === "comic_style_scope" &&
          (formData.daily_comic?.comic_style_mode ?? "fixed") === "fixed"
        )
          return false;
        if (!q || groupMatches) return true;
        const desc = (item.description || "").toLowerCase();
        const hint = (item.hint || "").toLowerCase();
        const key = fieldKey.toLowerCase();
        return desc.includes(q) || hint.includes(q) || key.includes(q);
      })
      .map(([fieldKey, item]) => ({
        key: fieldKey,
        schema: item,
        value:
          formData[displayedCategory]?.[fieldKey] !== undefined
            ? formData[displayedCategory][fieldKey]
            : item.default,
      }));
  }, [schema, displayedCategory, formData, searchQuery]);

  const renderingConfig = renderingRuntimeSchema.safeParse(formData.t2i_rendering ?? {});

  const templateRequirements = {
    engine: renderingConfig.success ? renderingConfig.data.template_engine : ("html" as const),
    formats: Array.isArray(formData.basic?.output_format)
      ? formData.basic.output_format.filter((value): value is string => typeof value === "string")
      : ["image"],
  };

  return {
    templateRequirements,
    templateCdnBaseUrl: renderingConfig.success ? renderingConfig.data.t2i_cdn_base_url : null,
    loading,
    loadError,
    saveError,
    optionsError,
    configLoaded,
    saving,
    isDirty,
    modifiedFields,
    originalConfig,
    schema,
    formData,
    providers,
    personas,
    categories,
    activeCategory: displayedCategory,
    currentGroupFields,
    activeGroupMeta: schema[displayedCategory],
    searchQuery,
    errors,
    groupErrorCounts,
    setSearchQuery,
    setActiveCategory,
    handleFieldChange,
    handleSave,
    handleReload: () => loadConfig(true),
  };
}
