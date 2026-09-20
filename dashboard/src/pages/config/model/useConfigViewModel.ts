import { useState, useEffect, useMemo } from "react";
import { message } from "antd";
import {
  fetchPluginConfig,
  fetchAvailableProviders,
  fetchAvailablePersonas,
  savePluginConfig,
  AvailableProvider,
  AvailablePersona,
} from "../../../entities/config/api/configApi";
import { PluginSchema } from "../../../entities/config/model/types";
import {
  validateConfigWithZod,
  validateSingleFieldWithZod,
} from "../../../entities/config/model/validation";

export function useConfigViewModel(onConfigSaved?: () => void) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [schema, setSchema] = useState<PluginSchema>({});
  const [originalConfig, setOriginalConfig] = useState<Record<string, Record<string, unknown>>>({});
  const [formData, setFormData] = useState<Record<string, Record<string, unknown>>>({});
  const [providers, setProviders] = useState<AvailableProvider[]>([]);
  const [personas, setPersonas] = useState<AvailablePersona[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("basic");
  const [searchQuery, setSearchQuery] = useState("");

  // 校验错误状态：按 分组Key -> 字段Key -> 错误信息 存储
  const [errors, setErrors] = useState<Record<string, Record<string, string>>>({});
  const [groupErrorCounts, setGroupErrorCounts] = useState<Record<string, number>>({});

  const loadConfig = async (isManual = false) => {
    setLoading(true);
    try {
      const [configData, providerList, personaList] = await Promise.allSettled([
        fetchPluginConfig(),
        fetchAvailableProviders(),
        fetchAvailablePersonas(),
      ]);

      if (providerList.status === "fulfilled") {
        setProviders(providerList.value || []);
      }

      if (personaList.status === "fulfilled") {
        setPersonas(personaList.value || []);
      }

      if (configData.status === "fulfilled" && configData.value) {
        const data = configData.value;
        setSchema(data.schema || {});
        setOriginalConfig(data.config || {});
        // 深拷贝一份 formData
        setFormData(JSON.parse(JSON.stringify(data.config || {})));

        const keys = Object.keys(data.schema || {});
        if (keys.length > 0 && (!activeCategory || !keys.includes(activeCategory))) {
          setActiveCategory(keys[0]);
        }
        if (isManual) {
          message.success("已重新读取最新配置");
        }
      }
    } catch {
      message.error("读取配置信息失败，请检查网络或后端状态");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFieldChange = (groupKey: string, fieldKey: string, value: unknown) => {
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
    const groupSchema = schema[groupKey];
    if (groupSchema && groupSchema.items) {
      let fieldSchema = groupSchema.items[fieldKey];
      // 处理嵌套字段路径（如 "topic_analysis_prompts.summary"）
      if (!fieldSchema && fieldKey.includes(".")) {
        const [parentKey, subKey] = fieldKey.split(".");
        const parentField = groupSchema.items[parentKey];
        if (parentField && parentField.items && typeof parentField.items === "object") {
          fieldSchema = (parentField.items as Record<string, typeof fieldSchema>)[subKey];
        }
      }

      if (fieldSchema) {
        const fieldError = validateSingleFieldWithZod(fieldKey, fieldSchema, value);
        setErrors((prevErrors) => {
          const nextErrors = { ...prevErrors };
          const groupErrors = { ...(nextErrors[groupKey] || {}) };

          if (fieldError) {
            groupErrors[fieldKey] = fieldError;
          } else {
            delete groupErrors[fieldKey];
          }

          if (Object.keys(groupErrors).length > 0) {
            nextErrors[groupKey] = groupErrors;
          } else {
            delete nextErrors[groupKey];
          }

          // 同步更新各分组错误计数
          setGroupErrorCounts((prevCounts) => {
            const nextCounts = { ...prevCounts };
            const count = Object.keys(groupErrors).length;
            if (count > 0) {
              nextCounts[groupKey] = count;
            } else {
              delete nextCounts[groupKey];
            }
            return nextCounts;
          });

          return nextErrors;
        });
      }
    }
  };

  const isDirty = useMemo(() => {
    return JSON.stringify(formData) !== JSON.stringify(originalConfig);
  }, [formData, originalConfig]);

  const handleSave = async () => {
    // 1. 保存前使用 Zod 执行严格校验
    const validationResult = validateConfigWithZod(formData, schema);

    if (!validationResult.isValid) {
      setErrors(validationResult.errorMap);
      setGroupErrorCounts(validationResult.groupErrorCounts);

      const firstError = validationResult.errors[0];
      if (firstError) {
        // 自动切换到存在错误的分组 Tab
        setActiveCategory(firstError.groupKey);

        // 提示人类可读的友好中文错误
        message.error(
          `【${firstError.groupLabel}】中的「${firstError.fieldLabel}」${firstError.message}，请检查该部分。`
        );

        // 平滑滚动定位并自动高亮聚焦到错误字段
        setTimeout(() => {
          const targetDom =
            document.getElementById(firstError.domId) ||
            document.getElementById(`cfg-field-${firstError.groupKey}-${firstError.fieldKey}`) ||
            document.getElementById(`cfg-field-${firstError.fieldKey}`);

          if (targetDom) {
            targetDom.scrollIntoView({ behavior: "smooth", block: "center" });
            const focusable = targetDom.querySelector<HTMLElement>(
              "input, select, textarea, button"
            );
            if (focusable) {
              focusable.focus();
            }
          }
        }, 120);
      }
      return;
    }

    // 校验通过，清理错误状态
    setErrors({});
    setGroupErrorCounts({});

    // 2. 提交保存
    setSaving(true);
    try {
      const res = await savePluginConfig(formData);
      if (res.success) {
        message.success(res.message || "配置已成功保存并生效");
        setOriginalConfig(JSON.parse(JSON.stringify(formData)));
        if (onConfigSaved) onConfigSaved();
      } else {
        message.error(res.message || "保存配置失败");
      }
    } catch {
      message.error("保存配置请求发生异常");
    } finally {
      setSaving(false);
    }
  };

  // 分组列表元数据（支持搜索过滤高亮与计数）
  const categories = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return Object.entries(schema).map(([key, group]) => {
      const groupDesc = group.description || key;
      const items = group.items || {};

      const visibleItems = Object.entries(items).filter(
        ([, item]) => !item.invisible && !item.hidden
      );

      let matchCount = 0;
      if (q) {
        if (groupDesc.toLowerCase().includes(q) || (group.hint && group.hint.toLowerCase().includes(q))) {
          matchCount += visibleItems.length;
        } else {
          for (const [, item] of visibleItems) {
            const desc = (item.description || "").toLowerCase();
            const hint = (item.hint || "").toLowerCase();
            if (desc.includes(q) || hint.includes(q)) {
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
  }, [schema, searchQuery]);

  // 当前激活分组的字段列表（应用搜索过滤，并过滤 invisible/hidden 隐藏兼容项）
  const currentGroupFields = useMemo(() => {
    if (!schema[activeCategory]) return [];
    const q = searchQuery.trim().toLowerCase();
    const groupItems = schema[activeCategory].items || {};

    return Object.entries(groupItems)
      .filter(([fieldKey, item]) => {
        // 过滤 schema 中声明为不可见或废弃迁移项
        if (item.invisible || item.hidden) return false;
        if (!q) return true;
        const desc = (item.description || "").toLowerCase();
        const hint = (item.hint || "").toLowerCase();
        const key = fieldKey.toLowerCase();
        return desc.includes(q) || hint.includes(q) || key.includes(q);
      })
      .map(([fieldKey, item]) => ({
        key: fieldKey,
        schema: item,
        value: formData[activeCategory]?.[fieldKey] !== undefined
          ? formData[activeCategory][fieldKey]
          : item.default,
      }));
  }, [schema, activeCategory, formData, searchQuery]);

  return {
    loading,
    saving,
    isDirty,
    schema,
    formData,
    providers,
    personas,
    categories,
    activeCategory,
    currentGroupFields,
    activeGroupMeta: schema[activeCategory],
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
