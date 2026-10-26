import { z } from "zod";

export const DEFAULT_TEMPLATE_CDN_BASE_URL = "https://cdn.jsdmirror.com";
export const TEMPLATE_CDN_PRESETS = [
  { value: DEFAULT_TEMPLATE_CDN_BASE_URL, label: "国内可先试 · JSDMirror（默认） · https://cdn.jsdmirror.com" },
  { value: "https://cdn.jsdmirror.cn", label: "国内备选 · JSDMirror CN · https://cdn.jsdmirror.cn" },
  { value: "https://jsd.cdn.noisework.cn", label: "备选 · NOISE · https://jsd.cdn.noisework.cn" },
  { value: "https://cdn.bili33.top", label: "备选 · 哔哩 CDN · https://cdn.bili33.top" },
  { value: "https://cdn.jsdelivr.net", label: "海外可先试 · jsDelivr · https://cdn.jsdelivr.net" },
  { value: "https://fastly.jsdelivr.net", label: "海外备选 · Fastly · https://fastly.jsdelivr.net" },
  { value: "https://gcore.jsdelivr.net", label: "海外备选 · Gcore · https://gcore.jsdelivr.net" },
];
export const CDN_FORMAT_ERROR = "请填完整的网站地址，例如 https://fastly.jsdelivr.net/，不要带账号密码、文件路径或 ?、# 后面的内容";

// 与后端 cdn_utils 共用边界用例；仅接受域名（国际化域名用 Punycode）或 IPv6。
const CDN_ROOT = /^https?:\/\/((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.?|\[[a-f0-9:]+\])(?::([0-9]{1,5}))?$/i;

export const cdnBaseUrlSchema = z.string({ error: "CDN 地址必须是字符串" })
  .max(2048, "CDN 地址不能超过 2048 个字符")
  .refine((value) => !/^\/+$/u.test(value.trim()), CDN_FORMAT_ERROR)
  .transform((value) => value.trim().replace(/\/+$/, ""))
  .refine((value) => {
    if (value === "") return true;
    const match = CDN_ROOT.exec(value);
    if (!match || (match[2] && (Number(match[2]) < 1 || Number(match[2]) > 65535))) return false;
    if (match[1].startsWith("[")) {
      try { new URL(value); } catch { return false; }
    }
    return true;
  }, CDN_FORMAT_ERROR);

// 方案结构与后端 rendering_config 保持一致，保存时保留扩展字段。
export const renderingStrategySchema = z.object({
  name: z.string({ error: "方案名称必须是文字" }).default("渲染方案"),
  priority: z.number({ error: "优先级必须是数字" }).int("优先级必须是整数").min(0, "优先级不能小于 0").max(10000, "优先级不能大于 10000").default(10),
  environment: z.enum(["Mainland", "Overseas"], { error: "请选择内地或海外资源环境" }).default("Overseas"),
  type: z.enum(["png", "jpeg"], { error: "请选择 PNG 或 JPEG 格式" }).default("png"),
  quality: z.number({ error: "图片质量必须是数字" }).int("图片质量必须是整数").min(1, "图片质量不能小于 1").max(100, "图片质量不能大于 100").default(80),
  device_scale: z.enum(["normal", "high", "ultra"], { error: "请选择有效的分辨率等级" }).default("high"),
  timeout: z.number({ error: "渲染超时必须是数字" }).int("渲染超时必须是整数").min(1000, "渲染超时不能小于 1000 毫秒").max(300000, "渲染超时不能大于 300000 毫秒").default(60000),
}).catchall(z.unknown());

export const renderingConfigSchema = z.object({
  t2i_cdn_base_url: z.string().optional(),
  t2i_mainland_cdn_base_url: z.string().optional(),
  t2i_overseas_cdn_base_url: z.string().optional(),
  t2i_rendering_strategies: z.array(renderingStrategySchema).optional(),
  t2i_atri_font_mirror: z.string().optional(),
}).catchall(z.unknown());

export type RenderingConfig = z.infer<typeof renderingConfigSchema>;

// 编辑时保留异常值，显示错误并允许修正；保存和业务使用严格契约。
export const renderingConfigLoadSchema = renderingConfigSchema.extend({
  t2i_cdn_base_url: z.unknown().optional(),
  t2i_mainland_cdn_base_url: z.unknown().optional(),
  t2i_overseas_cdn_base_url: z.unknown().optional(),
  t2i_rendering_strategies: z.unknown().optional(),
});

// 预览采用最高优先级方案的资源环境，旧配置继续使用原环境和地址。
export const renderingRuntimeSchema = z.object({
  t2i_cdn_base_url: cdnBaseUrlSchema.default(""),
  t2i_mainland_cdn_base_url: cdnBaseUrlSchema.default(""),
  t2i_overseas_cdn_base_url: cdnBaseUrlSchema.default(""),
  t2i_font_source: z.string().default("Overseas"),
  t2i_rendering_strategies: z.array(renderingStrategySchema).default([]),
}).transform((value) => {
  const first = [...value.t2i_rendering_strategies].sort((a, b) => a.priority - b.priority)[0];
  const environment = first?.environment ?? value.t2i_font_source;
  const baseUrl = environment === "Mainland"
    ? value.t2i_mainland_cdn_base_url : value.t2i_overseas_cdn_base_url;
  return { t2i_cdn_base_url: baseUrl || value.t2i_cdn_base_url || DEFAULT_TEMPLATE_CDN_BASE_URL };
});

export const renderingSaveSchema = renderingConfigSchema.extend({
  t2i_cdn_base_url: cdnBaseUrlSchema.optional(),
  t2i_mainland_cdn_base_url: cdnBaseUrlSchema.optional(),
  t2i_overseas_cdn_base_url: cdnBaseUrlSchema.optional(),
});
