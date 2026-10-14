import { z } from "zod";

export const DEFAULT_TEMPLATE_CDN_BASE_URL = "https://cdn.jsdmirror.com";
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

// 已声明的渲染配置契约；保存时仍需校验字段类型。
export const renderingConfigSchema = z.object({
  t2i_cdn_base_url: z.string().optional(),
  t2i_atri_font_mirror: z.string().optional(),
}).catchall(z.unknown());

export type RenderingConfig = z.infer<typeof renderingConfigSchema>;

// 编辑边界保留旧配置中的异常值，让表单展示错误并允许修正，不影响保存和业务投影的严格校验。
export const renderingConfigLoadSchema = renderingConfigSchema.extend({
  t2i_cdn_base_url: z.unknown().optional(),
});

// 业务投影不携带动态字段；缺省或空值使用默认地址，格式错误必须由调用方显示。
export const renderingRuntimeSchema = z.object({
  t2i_cdn_base_url: cdnBaseUrlSchema.default("")
    .transform((value) => value || DEFAULT_TEMPLATE_CDN_BASE_URL),
});

export const renderingSaveSchema = renderingConfigSchema.extend({
  t2i_cdn_base_url: cdnBaseUrlSchema.optional(),
});
