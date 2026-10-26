import { z } from "zod";

export const CUSTOM_RESOURCE_OPTION = "__custom__";
export const DEFAULT_CUSTOM_T2I_ENDPOINT = "http://127.0.0.1:8999/text2img";
export const DEFAULT_CUSTOM_T2I_REQUEST_TIMEOUT_MS = 40000;

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

export const fontBaseUrlSchema = z.string({ error: "字体地址必须是文字" })
  .max(2048, "字体地址不能超过 2048 个字符")
  .refine((value) => !/^\/+$/u.test(value.trim()), "请填写完整的 HTTP(S) 字体地址")
  .transform((raw, ctx) => {
    const value = raw.trim().replace(/\/+$/, "");
    if (!value) return "";
    const match = /^(https?):\/\/([^/]+)(\/.*)?$/i.exec(value);
    const origin = match ? `${match[1].toLowerCase()}://${match[2]}` : "";
    if (!match || /[\s\p{C}?#\\]/u.test(value) || !cdnBaseUrlSchema.safeParse(origin).success) {
      ctx.addIssue({ code: "custom", message: "请填写完整的 HTTP(S) 字体地址，不要带账号密码、查询参数或 # 片段" });
      return z.NEVER;
    }
    return origin + (match[3] || "");
  });

export const RENDERING_RESOURCE_DEFAULTS = {
  Mainland: { cdn_base_url: DEFAULT_TEMPLATE_CDN_BASE_URL, google_fonts: "https://fonts.loli.net", gstatic: "https://gstatic.loli.net" },
  Overseas: { cdn_base_url: DEFAULT_TEMPLATE_CDN_BASE_URL, google_fonts: "https://fonts.googleapis.com", gstatic: "https://fonts.gstatic.com" },
};

export const t2iEndpointSchema = z.string({ error: "服务地址必须是文字" })
  .max(2048, "服务地址不能超过 2048 个字符")
  .transform((raw, ctx) => {
    const value = raw.trim().replace(/\/+$/, "");
    const match = /^(https?):\/\/([^/]+)(\/.*)?$/i.exec(value);
    const origin = match ? `${match[1].toLowerCase()}://${match[2]}` : "";
    if (!match || /[\s\p{C}?#\\]/u.test(value) || !cdnBaseUrlSchema.safeParse(origin).success) {
      ctx.addIssue({ code: "custom", message: "请填写完整的 T2I 服务地址，例如 http://127.0.0.1:8999/text2img，不要带账号密码、查询参数或 # 片段" });
      return z.NEVER;
    }
    let path = match[3] || "";
    if (path.endsWith("/text2img/generate")) path = path.slice(0, -"/generate".length);
    if (!path.endsWith("/text2img")) path += "/text2img";
    return origin + path;
  });

// 方案结构与后端 rendering_config 保持一致，保存时保留扩展字段。
export const renderingStrategySchema = z.object({
  name: z.string({ error: "方案名称必须是文字" }).default("渲染方案"),
  priority: z.number({ error: "优先级必须是数字" }).int("优先级必须是整数").min(0, "优先级不能小于 0").max(10000, "优先级不能大于 10000").default(10),
  environment: z.enum(["Mainland", "Overseas"], { error: "请选择内地或海外资源环境" }).optional(),
  cdn_base_url: z.union([cdnBaseUrlSchema, z.literal(CUSTOM_RESOURCE_OPTION)]).optional(),
  google_fonts: z.union([fontBaseUrlSchema, z.literal(CUSTOM_RESOURCE_OPTION)]).optional(),
  gstatic: z.union([fontBaseUrlSchema, z.literal(CUSTOM_RESOURCE_OPTION)]).optional(),
  render_service: z.enum(["astrbot", "custom"], { error: "请选择有效的渲染方案类型" }).optional(),
  service_endpoint: z.string({ error: "服务地址必须是文字" }).trim().optional(),
  service_token: z.string({ error: "服务 Token 必须是文字" }).max(4096, "服务 Token 不能超过 4096 个字符").regex(/^[\x20-\x7e]*$/, "服务 Token 请使用英文、数字或常用符号，不能换行").transform((value) => value.trim()).default(""),
  type: z.enum(["png", "jpeg"], { error: "请选择 PNG 或 JPEG 格式" }).default("png"),
  quality: z.number({ error: "图片质量必须是数字" }).int("图片质量必须是整数").min(1, "图片质量不能小于 1").max(100, "图片质量不能大于 100").default(80),
  device_scale: z.enum(["normal", "high", "ultra"], { error: "请选择有效的分辨率等级" }).default("high"),
  request_timeout: z.number({ error: "请求等待上限必须是数字" }).int("请求等待上限必须是整数").min(1000, "请求等待上限不能小于 1000 毫秒").max(300000, "请求等待上限不能大于 300000 毫秒").optional(),
  timeout: z.number({ error: "渲染超时必须是数字" }).int("渲染超时必须是整数").min(1000, "渲染超时不能小于 1000 毫秒").max(300000, "渲染超时不能大于 300000 毫秒").default(20000),
}).catchall(z.unknown()).superRefine((value, ctx) => {
  for (const key of ["cdn_base_url", "google_fonts", "gstatic"] as const) {
    if (value[key] !== CUSTOM_RESOURCE_OPTION) continue;
    const raw = value[`custom_${key}`];
    const parsed = (key === "cdn_base_url" ? cdnBaseUrlSchema : fontBaseUrlSchema).safeParse(raw);
    if (!parsed.success || !parsed.data) ctx.addIssue({ code: "custom", path: [`custom_${key}`], message: "请填写完整的自定义资源地址" });
  }
  const service = value.render_service ?? (value.__template_key === "custom" ? "custom" : "astrbot");
  if (service === "custom") {
    const endpoint = t2iEndpointSchema.safeParse(value.service_endpoint ?? DEFAULT_CUSTOM_T2I_ENDPOINT);
    if (!endpoint.success) ctx.addIssue({ code: "custom", path: ["service_endpoint"], message: endpoint.error.issues[0].message });
  }
}).transform((value) => {
  for (const key of ["cdn_base_url", "google_fonts", "gstatic"] as const) {
    if (value[key] === CUSTOM_RESOURCE_OPTION) {
      const address = (key === "cdn_base_url" ? cdnBaseUrlSchema : fontBaseUrlSchema).parse(value[`custom_${key}`]);
      value[key] = address;
      value[`custom_${key}`] = address;
    }
  }
  const service = value.render_service ?? (value.__template_key === "custom" ? "custom" as const : "astrbot" as const);
  const environment = value.environment ?? (value.__template_key === "mainland" ? "Mainland" as const : "Overseas" as const);
  // 旧调用方式只用于迁移，保存后由条目类型唯一决定服务。
  const { render_service: _legacyService, ...plan } = value;
  return Object.assign(plan, {
    environment,
    ...(service === "custom" ? { request_timeout: value.request_timeout ?? DEFAULT_CUSTOM_T2I_REQUEST_TIMEOUT_MS } : {}),
    service_endpoint: service === "custom" ? t2iEndpointSchema.parse(value.service_endpoint ?? DEFAULT_CUSTOM_T2I_ENDPOINT) : value.service_endpoint ?? "",
    __template_key: service === "custom" ? "custom" : environment === "Mainland" ? "mainland" : "strategy",
  });
});

export const renderingConfigSchema = z.object({
  t2i_rendering_strategies: z.array(renderingStrategySchema).optional(),
  t2i_atri_font_mirror: z.string().optional(),
}).catchall(z.unknown());

export type RenderingConfig = z.infer<typeof renderingConfigSchema>;

// 编辑时保留异常值，显示错误并允许修正；保存和业务使用严格契约。
export const renderingConfigLoadSchema = renderingConfigSchema.extend({
  t2i_rendering_strategies: z.unknown().optional(),
});

// 运行时只读取每轮配置，旧资源键由后端迁移后移除。
const renderingResolvedSchema = renderingConfigSchema.transform((value) => Object.assign(value, {
  t2i_rendering_strategies: value.t2i_rendering_strategies?.map((plan) => {
    const defaults = RENDERING_RESOURCE_DEFAULTS[plan.environment];
    const resources = {
      cdn_base_url: plan.cdn_base_url || defaults.cdn_base_url,
      google_fonts: plan.google_fonts || defaults.google_fonts,
      gstatic: plan.gstatic || defaults.gstatic,
    };
    if (plan.__template_key === "custom") {
      for (const key of ["cdn_base_url", "google_fonts", "gstatic"] as const) {
        if (plan[key] === "") resources[key] = "";
      }
    }
    return Object.assign(plan, resources);
  }),
}));

export const renderingRuntimeSchema = renderingResolvedSchema.transform((value) => {
  const first = [...(value.t2i_rendering_strategies || [])].sort((a, b) => a.priority - b.priority)[0];
  return { t2i_cdn_base_url: first?.cdn_base_url || DEFAULT_TEMPLATE_CDN_BASE_URL };
});

export const renderingSaveSchema = renderingResolvedSchema.transform((value) => {
  if (value.t2i_rendering_strategies?.length === 0) {
    value.t2i_rendering_strategies = [
      { __template_key: "strategy", name: "海外方案", priority: 10 },
      { __template_key: "mainland", name: "内地方案", priority: 20 },
    ].map((preset) => {
      const plan = renderingStrategySchema.parse(preset);
      return { ...plan, ...RENDERING_RESOURCE_DEFAULTS[plan.environment] };
    });
  }
  value.t2i_rendering_strategies?.sort((a, b) => a.priority - b.priority);
  for (const key of ["t2i_cdn_base_url", "t2i_mainland_cdn_base_url", "t2i_mainland_google_fonts", "t2i_mainland_gstatic", "t2i_overseas_cdn_base_url", "t2i_overseas_google_fonts", "t2i_overseas_gstatic"]) {
    delete value[key];
  }
  return value;
});
