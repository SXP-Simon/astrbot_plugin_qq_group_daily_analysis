import type { GroupItem } from "../../../entities/group/model/types";
import { DEFAULT_WORDCLOUD_OPTIONS, wordCloudOptionsSchema } from "../../../entities/wordcloud/model/types";

export const WORDCLOUD_OVERRIDE_FIELDS = [
  { key: "enabled", label: "启用词云" },
  { key: "send_with_report", label: "随报告发送" },
  { key: "template", label: "词云模板" },
  { key: "font", label: "字体" },
  { key: "min_font_size", label: "最小字号" },
  { key: "max_font_size", label: "最大字号" },
  { key: "max_words", label: "最多展示词数" },
  { key: "word_spacing", label: "词语间距" },
  { key: "width", label: "画布宽度" },
  { key: "height", label: "画布高度" },
  { key: "rotation", label: "文字方向" },
  { key: "palette", label: "词语配色" },
  { key: "weight_mode", label: "词频权重" },
  { key: "min_frequency", label: "最低词频" },
  { key: "min_word_length", label: "最短词长" },
  { key: "stopwords", label: "额外停用词" },
  { key: "keep_words", label: "保留词 / 自定义词典" },
] as const;

export type WordCloudOverrideField = typeof WORDCLOUD_OVERRIDE_FIELDS[number]["key"];

export function isOverrideRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function isGroupUmo(value: string): boolean {
  return /^[^:\s]+:GroupMessage:[^\s]+$/.test(value);
}

export function buildOverrideGroupOptions(groups: GroupItem[], overrides: Record<string, unknown>) {
  const options = new Map<string, { value: string; label: string }>();
  for (const group of groups) {
    // 历史记录中的自动平台占位符不能当作可发送的会话标识。
    if (!group.platform || ["auto", "default", "all"].includes(group.platform)) continue;
    const umo = `${group.platform}:GroupMessage:${group.group_id}`;
    if (!isGroupUmo(umo)) continue;
    options.set(umo, { value: umo, label: `${group.group_name || group.group_id} · ${group.group_id} · ${group.platform}` });
  }
  for (const umo of Object.keys(overrides)) {
    if (!options.has(umo)) options.set(umo, { value: umo, label: `${umo}（已有覆盖）` });
  }
  return [...options.values()];
}

export function getEffectiveWordCloud(globalValue: Record<string, unknown>, override: Record<string, unknown>) {
  const { group_overrides: _groupOverrides, ...globalOptions } = globalValue;
  void _groupOverrides;
  return { ...DEFAULT_WORDCLOUD_OPTIONS, ...globalOptions, ...override };
}

export function getOverrideErrors(globalValue: Record<string, unknown>, override: Record<string, unknown>) {
  const result = wordCloudOptionsSchema.safeParse(getEffectiveWordCloud(globalValue, override));
  const errors: Record<string, string> = {};
  if (!result.success) {
    for (const issue of result.error.issues) errors[String(issue.path[0])] ??= issue.message;
  }
  return errors;
}

export function setOverrideFields(
  overrides: Record<string, unknown>,
  umo: string,
  keys: WordCloudOverrideField[],
  globalValue: Record<string, unknown>,
) {
  const current = overrides[umo];
  if (current !== undefined && !isOverrideRecord(current)) return overrides;
  const nextGroup = { ...current as Record<string, unknown> | undefined };
  const effective = getEffectiveWordCloud(globalValue, nextGroup);
  for (const field of WORDCLOUD_OVERRIDE_FIELDS) {
    if (keys.includes(field.key)) {
      if (!Object.prototype.hasOwnProperty.call(nextGroup, field.key)) nextGroup[field.key] = effective[field.key];
    } else delete nextGroup[field.key];
  }
  const next = { ...overrides };
  if (Object.keys(nextGroup).length) next[umo] = nextGroup;
  else delete next[umo];
  return next;
}

export function updateGroupOverride(overrides: Record<string, unknown>, umo: string, key: WordCloudOverrideField, value: unknown) {
  const current = overrides[umo];
  if (current !== undefined && !isOverrideRecord(current)) return overrides;
  return { ...overrides, [umo]: { ...current as Record<string, unknown> | undefined, [key]: value } };
}
