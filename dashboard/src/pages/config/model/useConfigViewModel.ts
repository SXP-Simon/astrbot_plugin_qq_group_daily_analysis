import { useState, useEffect, useMemo } from "react";
import { message } from "antd";
import {
  fetchPluginConfig,
  fetchAvailableProviders,
  savePluginConfig,
  AvailableProvider,
} from "../../../entities/config/api/configApi";
import { PluginSchema } from "../../../entities/config/model/types";

export function useConfigViewModel(onConfigSaved?: () => void) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [schema, setSchema] = useState<PluginSchema>({});
  const [originalConfig, setOriginalConfig] = useState<Record<string, Record<string, unknown>>>({});
  const [formData, setFormData] = useState<Record<string, Record<string, unknown>>>({});
  const [providers, setProviders] = useState<AvailableProvider[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("basic");
  const [searchQuery, setSearchQuery] = useState("");

  const loadConfig = async (isManual = false) => {
    setLoading(true);
    try {
      const [configData, providerList] = await Promise.allSettled([
        fetchPluginConfig(),
        fetchAvailableProviders(),
      ]);

      if (providerList.status === "fulfilled") {
        setProviders(providerList.value || []);
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
  };

  const isDirty = useMemo(() => {
    return JSON.stringify(formData) !== JSON.stringify(originalConfig);
  }, [formData, originalConfig]);

  const handleSave = async () => {
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

      let matchCount = 0;
      if (q) {
        if (groupDesc.toLowerCase().includes(q) || (group.hint && group.hint.toLowerCase().includes(q))) {
          matchCount += Object.keys(items).length;
        } else {
          for (const [, item] of Object.entries(items)) {
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
        totalFields: Object.keys(items).length,
        matchCount: q ? matchCount : undefined,
      };
    });
  }, [schema, searchQuery]);

  // 当前激活分组的字段列表（应用搜索过滤）
  const currentGroupFields = useMemo(() => {
    if (!schema[activeCategory]) return [];
    const q = searchQuery.trim().toLowerCase();
    const groupItems = schema[activeCategory].items || {};

    return Object.entries(groupItems)
      .filter(([fieldKey, item]) => {
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
    categories,
    activeCategory,
    currentGroupFields,
    activeGroupMeta: schema[activeCategory],
    searchQuery,
    setSearchQuery,
    setActiveCategory,
    handleFieldChange,
    handleSave,
    handleReload: () => loadConfig(true),
  };
}
