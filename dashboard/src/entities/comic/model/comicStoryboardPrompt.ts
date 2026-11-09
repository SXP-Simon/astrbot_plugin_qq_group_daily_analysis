import { expandAnalysisPrompt } from "../../config/model/promptSchemes";
import type { PromptVariable } from "../../config/model/types";

export const storyboardVariables: Record<string, PromptVariable> = {
  chat_content: {
    label: "核心话题列表",
    description: "填入每个核心话题的标题和详情。",
    required: true,
    example:
      "1. 话题: 群友筹划露营\n   详情: 大家讨论了路线和装备。\n2. 话题: 分享家常菜\n   详情: 群友交流了晚饭的做法。",
  },
  topic_count: {
    label: "话题数量",
    description: "填入本次核心话题数，用于约束漫画分格数量。",
    required: true,
    example: "2",
  },
};

const variables: Record<string, PromptVariable> = {
  ...storyboardVariables,
  max_count: storyboardVariables.topic_count,
};
const legacyVariables = new Map(Object.entries(variables));

export function readComicStoryboard(template: string) {
  const used = new Set<string>();
  let expanded: string;
  if (template.includes("$")) {
    const preview = expandAnalysisPrompt(template, variables);
    expanded = preview.expanded;
    for (const key of preview.used) used.add(key);
  } else {
    let invalidBraces = false;
    expanded = template.replace(/\{\{|\}\}|\{(\w+)\}|[{}]/g, (token, key?: string) => {
      if (token === "{{" || token === "}}") return token[0];
      const variable = key ? legacyVariables.get(key) : undefined;
      if (key && variable) {
        used.add(key);
        return variable.example;
      }
      invalidBraces = true;
      return token;
    });
    if (invalidBraces) {
      // 对齐运行时的 JSON 兼容分支，只替换已知变量并保留其他花括号。
      used.clear();
      expanded = template.replace(
        /(?<!\{)\{(chat_content|topic_count|max_count)\}(?!\})/g,
        (_, key: string) => {
          used.add(key);
          return variables[key].example;
        },
      );
    }
  }
  const hasLegacyModifiers =
    !template.includes("$") &&
    /\{(?:chat_content|topic_count|max_count)(?:!|:|\.|\[)/.test(template);
  const missing = Object.keys(storyboardVariables).filter(
    (key) => !used.has(key) && !(key === "topic_count" && used.has("max_count")),
  );
  return {
    expanded: hasLegacyModifiers ? null : expanded,
    error: hasLegacyModifiers
      ? "请改用不带格式修饰的变量，便于检查和预览。"
      : missing.length
        ? "请插入必填变量 " + missing.map((key) => "${" + key + "}").join("、")
        : "",
  };
}
