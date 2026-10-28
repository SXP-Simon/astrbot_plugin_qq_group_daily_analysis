import configSchema from "../../../../_conf_schema.json";
import { pluginConfigResponseSchema } from "../../entities/config/model/configContract";
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
