import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { PluginConfigData } from "../model/types";

export interface AvailableProvider {
  id: string;
  name: string;
  type?: string;
  label?: string;
}

export async function fetchPluginConfig(): Promise<PluginConfigData | null> {
  const res = await apiGet<PluginConfigData>("config");
  const data = extractData<PluginConfigData>(res);
  if (data && typeof data === "object") {
    if ("config" in data || "schema" in data) {
      return data;
    }
    const raw = data as Record<string, unknown>;
    if (raw.data && typeof raw.data === "object") {
      return raw.data as PluginConfigData;
    }
    return data;
  }
  return null;
}

export async function fetchAvailableProviders(): Promise<AvailableProvider[]> {
  const res = await apiGet<AvailableProvider[]>("providers");
  const data = extractData<AvailableProvider[]>(res);
  if (Array.isArray(data)) return data;
  return [];
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
