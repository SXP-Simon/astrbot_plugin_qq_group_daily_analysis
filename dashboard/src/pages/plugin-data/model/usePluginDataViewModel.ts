import { useState, useCallback } from "react";
import { message } from "antd";
import {
  fetchPluginDataOverview,
  clearAvatarCache,
  clearReports,
  clearTempFiles,
  clearCustomTemplates,
  clearConfigFiles,
  clearConfigBackups,
  PluginDataOverview,
} from "../../../entities/plugin-data/api/pluginDataApi";

const EMPTY_OVERVIEW: PluginDataOverview = {
  avatars: { count: 0, size_bytes: 0 },
  custom_templates: { count: 0, size_bytes: 0 },
  config_files: { count: 0, size_bytes: 0 },
  config_backups: { count: 0, size_bytes: 0 },
  reports: { count: 0, size_bytes: 0 },
  temp_files: { count: 0, size_bytes: 0 },
};

export function usePluginDataViewModel() {
  const [overview, setOverview] = useState<PluginDataOverview>(EMPTY_OVERVIEW);
  const [loading, setLoading] = useState(false);
  const [clearing, setClearing] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchPluginDataOverview();
      setOverview(data);
    } catch (e) {
      message.error("加载数据概览失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const runClear = async (
    key: string,
    fn: () => Promise<number>,
    label: string
  ) => {
    setClearing(key);
    try {
      const deleted = await fn();
      message.success(`已清除 ${deleted} 个${label}文件`);
      await refresh();
    } catch {
      message.error(`清除${label}失败`);
    } finally {
      setClearing(null);
    }
  };

  return {
    overview,
    loading,
    clearing,
    refresh,
    clearAvatarCache: () => runClear("avatars", clearAvatarCache, "头像缓存"),
    clearReports: () => runClear("reports", clearReports, "历史报告"),
    clearTempFiles: () => runClear("temp_files", clearTempFiles, "临时渲染缓存"),
    clearCustomTemplates: () =>
      runClear("custom_templates", clearCustomTemplates, "自定义模板备份"),
    clearConfigFiles: () =>
      runClear("config_files", clearConfigFiles, "配置参考素材"),
    clearConfigBackups: () =>
      runClear("config_backups", clearConfigBackups, "配置历史自动备份"),
  };
}
