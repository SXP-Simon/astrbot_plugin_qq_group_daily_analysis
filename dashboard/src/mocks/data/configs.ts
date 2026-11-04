import configSchema from "../../../../_conf_schema.json";
import { z } from "zod";
import { pluginConfigResponseSchema, pluginConfigSaveSchema } from "../../entities/config/model/configContract";
import type { PluginConfigData, SchemaFieldItem } from "../../entities/config/model/types";
import type { AvailablePersona, AvailableProvider } from "../../entities/config/api/configApi";

function defaults(items: Record<string, SchemaFieldItem>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(items).flatMap(([key, field]) => {
    if (field.default !== undefined) return [[key, structuredClone(field.default)]];
    if (field.type === "object" && field.items && !("type" in field.items)) {
      return [[key, defaults(field.items as Record<string, SchemaFieldItem>)]];
    }
    return [];
  }));
}

const schema = pluginConfigResponseSchema.parse({
  config: {},
  schema: Object.fromEntries([
    ["t2i_rendering", configSchema.t2i_rendering],
    ...Object.entries(configSchema).filter(([key]) => key !== "t2i_rendering"),
  ]),
}).schema;

export const mockPluginConfig: PluginConfigData = {
  config: Object.fromEntries(Object.entries(schema).map(([key, group]) => [key, defaults(group.items)])),
  schema,
};

let configVersion = 0;
export const configMockHandlers = {
  "GET config": () => ({ status: "ok", data: structuredClone({ ...mockPluginConfig, revision: String(configVersion).padStart(64, "0") }) }),
  "POST config": (body?: unknown) => {
    const input = z.object({ config: pluginConfigSaveSchema, revision: z.string().regex(/^[0-9a-f]{64}$/).optional() }).safeParse(body);
    if (!input.success) return { status: "error", message: "缺少有效的配置数据或版本" };
    if (input.data.revision !== undefined && input.data.revision !== String(configVersion).padStart(64, "0")) {
      return { status: "error", message: "配置已被其他页面修改，请重新读取后再保存。当前改动尚未保存。" };
    }
    mockPluginConfig.config = { ...mockPluginConfig.config, ...structuredClone(input.data.config) };
    configVersion += 1;
    return { status: "ok", revision: String(configVersion).padStart(64, "0"), message: "配置已成功保存并持久化生效" };
  },
};

mockPluginConfig.config.daily_comic.comic_characters = [{
  __template_key: "character", name: "示例角色", enable: true,
  reference_images: ["files/daily_comic/comic_characters/templates/character/reference_images/character.png"],
}];

// 演示原生渲染与 HTML 后备，生产默认值仍由配置契约管理。
const rendering = mockPluginConfig.config.t2i_rendering;
if (rendering) rendering.t2i_rendering_strategies = [
  { __template_key: "typst", name: "Typst 本地排版", priority: 5, timeout: 30000, type: "png", quality: 90, cdn_base_url: "https://cdn.jsdmirror.com" },
  ...(Array.isArray(rendering.t2i_rendering_strategies) ? rendering.t2i_rendering_strategies : []),
];

export const mockProviders: AvailableProvider[] = [
  { id: "deepseek-chat", name: "DeepSeek Chat (V3)", type: "openai_compatible", label: "DeepSeek Official" },
  { id: "openai", name: "OpenAI GPT-4o", type: "openai", label: "OpenAI Main" },
  { id: "claude-3-5-sonnet", name: "Claude 3.5 Sonnet", type: "anthropic", label: "Anthropic Direct" },
  { id: "ollama_local", name: "Ollama (Local Qwen2.5-7B)", type: "openai_compatible", label: "Local Private" },
];

export const mockPersonas: AvailablePersona[] = [
  { id: "default", name: "标准毒舌总结官", label: "语气幽默锐利、一针见血提炼群热点" },
  { id: "cute_maid", name: "贴心女仆看板娘", label: "温柔软萌、善解人意、鼓励群友活跃" },
  { id: "academic_scholar", name: "严谨学术研究员", label: "客观中立、条理清晰、结构化要点提炼" },
  { id: "cyber_hacker", name: "赛博极客观察者", label: "科技感、暗黑极客风、冷峻幽默" },
];
