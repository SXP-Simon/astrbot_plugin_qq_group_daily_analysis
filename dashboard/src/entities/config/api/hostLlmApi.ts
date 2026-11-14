import { apiGet, extractData } from "@/shared/api/bridge";
import { hostLlmConfigSchema, type HostLlmConfig } from "@/entities/config/model/hostLlmConfig";

export async function fetchHostLlmConfig(session?: {
  platform: string;
  group_id: string;
}): Promise<HostLlmConfig> {
  // 宿主回执丢失时结束加载，让用户可以再次刷新；复用通信层的超时处理。
  const response = await apiGet<unknown>(
    "config/host-llm",
    session ? { platform_id: session.platform, group_id: session.group_id } : {},
    15_000,
  );
  const parsed = hostLlmConfigSchema.safeParse(extractData<unknown>(response));
  if (!parsed.success) throw new Error("无法读取宿主模型配置，请稍后刷新或检查宿主状态。");
  return parsed.data;
}
