import { cdnBaseUrlSchema, fontBaseUrlSchema, renderingStrategySchema } from "./renderingConfig";
import { z } from "zod";
import { PluginSchema, SchemaFieldItem } from "./types";
import { isFieldVisible } from "./visibility";

export interface ConfigValidationError {
  groupKey: string;
  groupLabel: string;
  fieldKey: string;
  fieldLabel: string;
  message: string;
  path: string;
  domId: string;
}

export interface ConfigValidationResult {
  isValid: boolean;
  errors: ConfigValidationError[];
  errorMap: Record<string, Record<string, string>>;
  groupErrorCounts: Record<string, number>;
}

const TIME_REGEX = /^([01]?\d|2[0-3]):[0-5]\d$/;

/** 校验声明字段，递归检查对象与方案，保留未声明的扩展值。 */
export function buildFieldZodSchema(fieldKey: string, field: SchemaFieldItem): z.ZodType {
  if (fieldKey === "cdn_base_url") return cdnBaseUrlSchema.optional();
  if (["google_fonts", "gstatic"].includes(fieldKey)) return fontBaseUrlSchema.optional();
  if (fieldKey === "t2i_rendering_strategies") return z.array(renderingStrategySchema).optional();

  return z.unknown().superRefine((value, ctx) => {
    if (value === undefined || value === null) return;
    switch (field.type) {
      case "int":
      case "float": {
        if (
          typeof value !== "number" ||
          !Number.isFinite(value) ||
          (field.type === "int" && !Number.isInteger(value))
        ) {
          ctx.addIssue({
            code: "custom",
            message: field.type === "int" ? "必须填写有效的整数" : "必须填写有效的数字",
          });
          return;
        }
        if (typeof field.min === "number" && value < field.min)
          ctx.addIssue({ code: "custom", message: `数值不能小于 ${field.min}` });
        if (typeof field.max === "number" && value > field.max)
          ctx.addIssue({ code: "custom", message: `数值不能大于 ${field.max}` });
        break;
      }
      case "bool":
        if (typeof value !== "boolean")
          ctx.addIssue({ code: "custom", message: "必须为布尔值（开关状态）" });
        break;
      case "object": {
        if (typeof value !== "object" || Array.isArray(value)) {
          ctx.addIssue({ code: "custom", message: "请填写有效的 JSON 对象，修正后再保存。" });
          return;
        }
        const data = value as Record<string, unknown>;
        const items = field.items;
        if (items && typeof items.type !== "string") {
          for (const [key, child] of Object.entries(items as Record<string, SchemaFieldItem>)) {
            if (child.hidden || !isFieldVisible(child, { current: data })) continue;
            const result = buildFieldZodSchema(key, child).safeParse(data[key] ?? child.default);
            if (!result.success)
              for (const issue of result.error.issues)
                ctx.addIssue({
                  code: "custom",
                  path: [key, ...issue.path],
                  message: `${child.description || key}：${issue.message}`,
                });
          }
        }
        break;
      }
      case "list":
      case "template_list": {
        if (!Array.isArray(value)) {
          ctx.addIssue({ code: "custom", message: "列表数据格式不合法，必须为数组" });
          return;
        }
        const values: unknown[] = value;
        values.forEach((item, index) => {
          if (field.type === "template_list") {
            if (!item || typeof item !== "object" || Array.isArray(item)) {
              ctx.addIssue({
                code: "custom",
                path: [index],
                message: `第 ${index + 1} 个方案必须是配置对象`,
              });
              return;
            }
            const data = item as Record<string, unknown>;
            const templates = field.templates;
            if (templates && Object.keys(templates).length) {
              const key =
                data.__template_key ??
                (Object.keys(templates).length === 1 ? Object.keys(templates)[0] : undefined);
              const template = typeof key === "string" ? templates[key] : undefined;
              if (!template) {
                ctx.addIssue({
                  code: "custom",
                  path: [index],
                  message: `第 ${index + 1} 个方案请选择有效的类型`,
                });
                return;
              }
              const result = buildFieldZodSchema(fieldKey, {
                type: "object",
                items: template.items,
              }).safeParse(data);
              if (!result.success)
                for (const issue of result.error.issues)
                  ctx.addIssue({
                    code: "custom",
                    path: [index, ...issue.path],
                    message: `第 ${index + 1} 个方案：${issue.message}`,
                  });
            }
          } else if (fieldKey === "auto_analysis_time") {
            const time = typeof item === "string" ? item.trim().replace(/：/g, ":") : "";
            const parts = /^(\d{1,2}):(\d{1,2})$/.exec(time);
            if (!parts || Number(parts[1]) > 23 || Number(parts[2]) > 59)
              ctx.addIssue({
                code: "custom",
                path: [index],
                message: "自动分析时间请使用 00:00–23:59 范围内的 HH:MM 格式",
              });
          }
        });
        break;
      }
      case "file":
        if (
          typeof value !== "string" &&
          !(Array.isArray(value) && value.every((item: unknown) => typeof item === "string"))
        )
          ctx.addIssue({ code: "custom", message: "文件路径必须是文字或路径列表" });
        break;
      case "string":
      case "text":
        if (typeof value !== "string") {
          ctx.addIssue({ code: "custom", message: "必须填写文字" });
          return;
        }
        if (
          fieldKey === "daily_schedule_time" &&
          value &&
          !TIME_REGEX.test(value.trim().replace(/：/g, ":"))
        )
          ctx.addIssue({
            code: "custom",
            message: "时间格式不正确，请输入 24 小时制 HH:MM 格式（如 23:30）",
          });
        if (value.trim() && fieldKey === "profile_mapping_config") {
          try {
            const mapping: unknown = JSON.parse(value);
            if (!mapping || typeof mapping !== "object" || Array.isArray(mapping))
              ctx.addIssue({ code: "custom", message: "请填写有效的 JSON 对象" });
          } catch {
            ctx.addIssue({
              code: "custom",
              message: "请填写有效的 JSON 对象，检查括号、引号和逗号",
            });
          }
        }
        break;
    }
    if (field.options?.length && !fieldKey.includes("report_template")) {
      const choices: unknown[] = field.type === "list" && Array.isArray(value) ? value : [value];
      if (choices.some((item) => item !== "" && !field.options!.some((option) => option === item)))
        ctx.addIssue({ code: "custom", message: "选项无效，请从预设选项中选择" });
    }
  });
}

/**
 * 校验单个字段值，返回错误消息或 null
 */
export function validateSingleFieldWithZod(
  fieldKey: string,
  field: SchemaFieldItem,
  value: unknown,
): string | null {
  const validator = buildFieldZodSchema(fieldKey, field);
  const result = validator.safeParse(value);
  if (!result.success) {
    return result.error.issues[0]?.message || "填写内容不符合规范";
  }
  return null;
}

/**
 * 校验整个表单数据，返回格式化错误信息与快速索引映射
 */
export function validateConfigWithZod(
  formData: Record<string, Record<string, unknown>>,
  schema: PluginSchema,
): ConfigValidationResult {
  const errors: ConfigValidationError[] = [];
  const errorMap: Record<string, Record<string, string>> = {};
  const groupErrorCounts: Record<string, number> = {};

  Object.entries(schema).forEach(([groupKey, group]) => {
    const groupLabel = group.description || groupKey;
    const groupData = formData[groupKey] || {};
    const groupItems = group.items || {};

    Object.entries(groupItems).forEach(([fieldKey, field]) => {
      if (field.hidden || !isFieldVisible(field, formData)) return;

      const fieldLabel = field.description || fieldKey;
      const value = groupData[fieldKey] !== undefined ? groupData[fieldKey] : field.default;
      const domId = `cfg-field-${groupKey}-${fieldKey}`;

      const errorMsg = validateSingleFieldWithZod(fieldKey, field, value);
      if (errorMsg) {
        errors.push({
          groupKey,
          groupLabel,
          fieldKey,
          fieldLabel,
          message: errorMsg,
          path: `${groupKey}.${fieldKey}`,
          domId,
        });

        if (!errorMap[groupKey]) {
          errorMap[groupKey] = {};
        }
        errorMap[groupKey][fieldKey] = errorMsg;
        groupErrorCounts[groupKey] = (groupErrorCounts[groupKey] || 0) + 1;
      }
    });
  });

  return {
    isValid: errors.length === 0,
    errors,
    errorMap,
    groupErrorCounts,
  };
}
