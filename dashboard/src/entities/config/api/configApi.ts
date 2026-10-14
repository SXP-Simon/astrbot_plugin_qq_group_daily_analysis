import { z } from "zod";
import { pluginConfigResponseSchema, pluginConfigSaveSchema } from "../model/configContract";
import { cdnBaseUrlSchema } from "../model/renderingConfig";
import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { PluginConfigData } from "../model/types";
import {
  templateCdnProbeSchema,
  type TemplateCdnProbe,
  type TemplateCdnProbeRequest,
} from "../model/cdnProbe";

export async function testTemplateCdn(baseUrl: string): Promise<TemplateCdnProbe> {
  const input = cdnBaseUrlSchema.safeParse(baseUrl);
  if (!input.success) throw new Error(input.error.issues[0].message);
  const body: TemplateCdnProbeRequest = { base_url: input.data };
  const response = await apiPost<unknown>("config/test-template-cdn", body);
  const data = extractData<unknown>(response);
  const parsed = templateCdnProbeSchema.safeParse(data);
  if (parsed.success) return parsed.data;

  const errorMessage = data && typeof data === "object" && "message" in data
    ? data.message : response?.message;
  throw new Error(typeof errorMessage === "string" && errorMessage
    ? errorMessage : "没有收到检测结果，请刷新页面后重试。");
}

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

export async function fetchPluginConfig(): Promise<PluginConfigData> {
  const res = await apiGet<unknown>("config");
  const parsed = pluginConfigResponseSchema.safeParse(extractData<unknown>(res));
  if (!parsed.success) {
    const issue = parsed.error.issues[0];
    throw new Error(`配置响应结构无效（${issue.path.join(".") || "根对象"}），请检查插件版本和后端响应`);
  }
  return parsed.data;
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
    const input = pluginConfigSaveSchema.safeParse(config);
    if (!input.success) return { success: false, message: input.error.issues[0].message };
    const payload = input.data;
    const res = await apiPost<unknown>("config", { config: payload });
    const envelope = z.object({
      status: z.string().optional(),
      code: z.number().optional(),
      error: z.unknown().optional(),
      message: z.string().optional(),
      data: z.unknown().optional(),
    });
    let response: unknown = res;
    // 检查宿主与插件两层信封，不能把内层保存失败当成成功。
    for (let depth = 0; depth < 2; depth += 1) {
      const parsed = envelope.safeParse(response);
      if (!parsed.success) break;
      const raw = parsed.data;
      if (raw.status === "error" || raw.error ||
          (raw.code !== undefined && raw.code !== 0 && raw.code !== 200)) {
        return { success: false, message: raw.message || "保存配置失败" };
      }
      const nested = envelope.safeParse(raw.data);
      if (depth === 0 && nested.success && nested.data.status !== undefined) {
        response = raw.data;
        continue;
      }
      if (raw.status === "ok" || raw.status === "success") {
        return { success: true, message: raw.message || "配置已成功保存并持久化生效" };
      }
      break;
    }
    return { success: false, message: "保存配置失败，未收到有效的成功响应" };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return { success: false, message: msg || "保存配置请求失败" };
  }
}

export async function uploadConfigFile(
  file: File,
  configKey?: string
): Promise<{ path: string } | null> {
  try {
    const base64Data = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = (e) => reject(e);
      reader.readAsDataURL(file);
    });

    const res = await apiPost<{ path?: string }>("config/upload_file", {
      filename: file.name,
      file_data: base64Data,
      config_key: configKey,
    });
    const data = extractData<{ path?: string }>(res);
    if (data && typeof data === "object" && data.path) {
      return { path: data.path };
    }
  } catch (e) {
    console.error("uploadConfigFile error:", e);
  }
  return null;
}

export async function fetchConfigFileContent(
  path: string
): Promise<{ data_url: string; filename?: string } | null> {
  const res = await apiGet<{ data_url?: string; filename?: string }>(
    "config/file/content",
    { path }
  );
  const data = extractData<{ data_url?: string; filename?: string }>(res);
  if (data && typeof data === "object" && data.data_url) {
    return { data_url: data.data_url, filename: data.filename };
  }
  return null;
}
