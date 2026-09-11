import { z } from "zod";
import { PluginSchema, SchemaFieldItem } from "./types";

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

/**
 * 为单个 Schema 字段构建对应的 Zod 校验器
 */
export function buildFieldZodSchema(
  fieldKey: string,
  field: SchemaFieldItem
): z.ZodType {
  // 1. 单选下拉选项校验（排除 list 多选类型以及可自定义的 report_template）
  if (
    field.type !== "list" &&
    Array.isArray(field.options) &&
    field.options.length > 0 &&
    fieldKey !== "report_template" &&
    !fieldKey.includes("report_template")
  ) {
    return z.any().superRefine((val, ctx) => {
      if (val === undefined || val === null || val === "") return;
      if (!field.options!.includes(val as string | number)) {
        ctx.addIssue({
          code: "custom",
          message: `选项无效，请从预设选项中选择（可选: ${field.options!.slice(0, 4).join(", ")}${
            field.options!.length > 4 ? " 等" : ""
          }）`,
        });
      }
    });
  }

  // 2. 按数据类型分支校验
  switch (field.type) {
    case "int":
      return z.any().superRefine((val, ctx) => {
        if (val === undefined || val === null || val === "") return;
        const num = typeof val === "number" ? val : Number(val);
        if (isNaN(num) || !Number.isInteger(num)) {
          ctx.addIssue({
            code: "custom",
            message: "必须填写有效的整数",
          });
          return;
        }
        if (typeof field.min === "number" && num < field.min) {
          ctx.addIssue({
            code: "custom",
            message: `数值不能小于 ${field.min}`,
          });
        }
        if (typeof field.max === "number" && num > field.max) {
          ctx.addIssue({
            code: "custom",
            message: `数值不能大于 ${field.max}`,
          });
        }
      });

    case "float":
      return z.any().superRefine((val, ctx) => {
        if (val === undefined || val === null || val === "") return;
        const num = typeof val === "number" ? val : Number(val);
        if (isNaN(num)) {
          ctx.addIssue({
            code: "custom",
            message: "必须填写有效的数字",
          });
          return;
        }
        if (typeof field.min === "number" && num < field.min) {
          ctx.addIssue({
            code: "custom",
            message: `数值不能小于 ${field.min}`,
          });
        }
        if (typeof field.max === "number" && num > field.max) {
          ctx.addIssue({
            code: "custom",
            message: `数值不能大于 ${field.max}`,
          });
        }
      });

    case "bool":
      return z.any().superRefine((val, ctx) => {
        if (
          typeof val !== "boolean" &&
          val !== "true" &&
          val !== "false" &&
          val !== undefined &&
          val !== null
        ) {
          ctx.addIssue({
            code: "custom",
            message: "必须为布尔值（开关状态）",
          });
        }
      });

    case "list":
      return z.any().superRefine((val, ctx) => {
        if (val === undefined || val === null) return;
        if (!Array.isArray(val)) {
          ctx.addIssue({
            code: "custom",
            message: "列表数据格式不合法，必须为数组",
          });
          return;
        }

        // 如果是多选枚举列表 (如 output_format)
        if (Array.isArray(field.options) && field.options.length > 0) {
          for (const item of val) {
            if (!field.options.includes(item as string | number)) {
              ctx.addIssue({
                code: "custom",
                message: `包含无效的选项「${item}」`,
              });
            }
          }
        }
      });

    case "template_list":
      return z.any().superRefine((val, ctx) => {
        if (val === undefined || val === null) return;
        if (!Array.isArray(val)) {
          ctx.addIssue({
            code: "custom",
            message: "方案列表格式不正确",
          });
          return;
        }
        val.forEach((item, idx) => {
          if (!item || typeof item !== "object") {
            ctx.addIssue({
              code: "custom",
              message: `第 ${idx + 1} 个方案配置数据不合法`,
            });
          }
        });
      });

    case "file":
      return z.any().superRefine((val, ctx) => {
        if (val === undefined || val === null || val === "") return;
        if (typeof val !== "string" && !Array.isArray(val)) {
          ctx.addIssue({
            code: "custom",
            message: "文件路径格式不正确",
          });
        }
      });

    case "string":
    case "text":
    default:
      return z.any().superRefine((val, ctx) => {
        if (val === undefined || val === null || val === "") return;

        // 1. 定时时间格式检测 (如 daily_schedule_time: "23:00")
        if (
          fieldKey === "daily_schedule_time" ||
          (fieldKey.includes("time") && typeof val === "string" && val.includes(":"))
        ) {
          if (typeof val === "string" && !TIME_REGEX.test(val.trim())) {
            ctx.addIssue({
              code: "custom",
              message: "时间格式不正确，请输入 24 小时制 HH:MM 格式（如 23:30）",
            });
            return;
          }
        }

        // 2. JSON 字符串格式检测
        if (
          typeof val === "string" &&
          val.trim() &&
          (fieldKey.includes("json") ||
            fieldKey.includes("mapping") ||
            fieldKey.includes("overrides"))
        ) {
          const trimmed = val.trim();
          if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
            try {
              JSON.parse(trimmed);
            } catch (err) {
              ctx.addIssue({
                code: "custom",
                message: `JSON 语法解析失败: ${(err as Error).message}`,
              });
            }
          }
        }
      });
  }
}

/**
 * 校验单个字段值，返回错误消息或 null
 */
export function validateSingleFieldWithZod(
  fieldKey: string,
  field: SchemaFieldItem,
  value: unknown
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
  schema: PluginSchema
): ConfigValidationResult {
  const errors: ConfigValidationError[] = [];
  const errorMap: Record<string, Record<string, string>> = {};
  const groupErrorCounts: Record<string, number> = {};

  Object.entries(schema).forEach(([groupKey, group]) => {
    const groupLabel = group.description || groupKey;
    const groupData = formData[groupKey] || {};
    const groupItems = group.items || {};

    Object.entries(groupItems).forEach(([fieldKey, field]) => {
      if (field.invisible || field.hidden) return;

      const fieldLabel = field.description || fieldKey;
      const value =
        groupData[fieldKey] !== undefined ? groupData[fieldKey] : field.default;
      const domId = `cfg-field-${groupKey}-${fieldKey}`;

      // 递归处理嵌套 object 字段
      if (
        field.type === "object" &&
        field.items &&
        typeof field.items === "object" &&
        !Array.isArray(field.items)
      ) {
        const subItems = field.items as Record<string, SchemaFieldItem>;
        const objVal = (typeof value === "object" && value !== null ? value : {}) as Record<string, unknown>;

        Object.entries(subItems).forEach(([subKey, subField]) => {
          if (subField.invisible || subField.hidden) return;
          const subLabel = `${fieldLabel} - ${subField.description || subKey}`;
          const subValue = objVal[subKey] !== undefined ? objVal[subKey] : subField.default;
          const subDomId = `cfg-field-${groupKey}-${fieldKey}-${subKey}`;
          const subError = validateSingleFieldWithZod(subKey, subField, subValue);

          if (subError) {
            errors.push({
              groupKey,
              groupLabel,
              fieldKey: `${fieldKey}.${subKey}`,
              fieldLabel: subLabel,
              message: subError,
              path: `${groupKey}.${fieldKey}.${subKey}`,
              domId: subDomId,
            });

            if (!errorMap[groupKey]) {
              errorMap[groupKey] = {};
            }
            errorMap[groupKey][`${fieldKey}.${subKey}`] = subError;
            groupErrorCounts[groupKey] = (groupErrorCounts[groupKey] || 0) + 1;
          }
        });
        return;
      }

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
