import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { PluginConfigData } from "../model/types";

export interface AvailableProvider {
  id: string;
  name: string;
  type?: string;
  label?: string;
}

export interface AvailablePersona {
  id: string;
  name: string;
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

export async function fetchAvailablePersonas(): Promise<AvailablePersona[]> {
  const res = await apiGet<AvailablePersona[]>("personas");
  const data = extractData<AvailablePersona[]>(res);
  if (Array.isArray(data)) return data;
  return [];
}

export async function savePluginConfig(
  config: Record<string, unknown>
): Promise<{ success: boolean; message?: string }> {
  try {
    const res = await apiPost("config", { config });
    if (res !== null && res !== undefined) {
      const raw = res as Record<string, unknown>;
      // 只有在明确返回 error 状态时才判定为失败
      if (
        raw.status === "error" ||
        raw.error ||
        (typeof raw.code === "number" && raw.code !== 0 && raw.code !== 200)
      ) {
        const errMsg =
          (raw.message as string) || (raw.error as string) || "保存配置失败";
        return { success: false, message: errMsg };
      }

      const msg =
        (raw.message as string) ||
        (typeof raw.data === "object" &&
          raw.data &&
          ((raw.data as Record<string, unknown>).message as string)) ||
        "配置已成功保存并持久化生效";

      return { success: true, message: msg };
    }
    return { success: false, message: "保存配置失败，未收到响应" };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return { success: false, message: msg || "保存配置请求失败" };
  }
}
