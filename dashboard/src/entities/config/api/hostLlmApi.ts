import { apiGet, extractData } from "@/shared/api/bridge";
import { hostLlmConfigSchema, type HostLlmConfig } from "@/entities/config/model/hostLlmConfig";

export async function fetchHostLlmConfig(session?: {
  platform: string;
  group_id: string;
}): Promise<HostLlmConfig> {
  const response = await apiGet<unknown>(
    "config/host-llm",
    session ? { platform_id: session.platform, group_id: session.group_id } : {},
  );
  const parsed = hostLlmConfigSchema.safeParse(extractData<unknown>(response));
  if (!parsed.success) throw new Error("无法读取宿主模型配置，请稍后刷新或检查宿主状态。");
  return parsed.data;
}
