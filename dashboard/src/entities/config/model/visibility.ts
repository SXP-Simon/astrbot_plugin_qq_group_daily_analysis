import { SchemaFieldItem } from "./types";

/** 解析条件依赖项的当前值：支持 "分组.字段" 与跨分组的裸字段名 */
export function resolveDependencyValue(
  formData: Record<string, Record<string, unknown>>,
  key: string,
): unknown {
  if (key.includes(".")) {
    const [groupKey, fieldKey] = key.split(".", 2);
    return formData[groupKey]?.[fieldKey];
  }
  for (const group of Object.values(formData)) {
    if (group && Object.prototype.hasOwnProperty.call(group, key)) {
      return group[key];
    }
  }
  return undefined;
}

/**
 * 字段是否满足显示条件（schema 的官方键 `condition`）。
 *
 * 依赖项当前值**等于**声明值即显示（单值相等，与维护者在 `size`/`custom_size` 上的用法一致）；
 * 若声明值是数组，则命中任一即显示（兼容旧写法）；未声明 condition 的字段恒显示。
 * 该键是 AstrBot 官方 schema 能力，官方 WebUI 与插件自带面板都会按它隐藏字段。
 */
export function isFieldVisible(
  item: SchemaFieldItem,
  formData: Record<string, Record<string, unknown>>,
): boolean {
  if (item.invisible) return false;
  const condition = item.condition;
  if (!condition || typeof condition !== "object") return true;
  return Object.entries(condition).every(([key, expected]) => {
    const value = resolveDependencyValue(formData, key);
    if (Array.isArray(expected)) {
      return expected.some((candidate) => String(candidate) === String(value));
    }
    return String(expected) === String(value);
  });
}
