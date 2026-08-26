import { apiGet, apiPost } from "../../../shared/api/bridge";
import { PluginConfigData } from "../model/types";

export async function fetchPluginConfig(): Promise<PluginConfigData | null> {
  const res = await apiGet<PluginConfigData>("config");
  if (res && res.data) {
    return res.data;
  }
  return null;
}

export async function savePluginConfig(
  config: Record<string, unknown>
): Promise<{ success: boolean; message?: string }> {
  const res = await apiPost("config", { config });
  if (res && res.status === "ok") {
    return { success: true, message: res.message || "配置已成功保存" };
  }
  return { success: false, message: res?.message || "保存配置失败" };
}
