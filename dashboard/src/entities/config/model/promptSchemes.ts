import { z } from "zod";
import type { PromptVariable } from "./types";

const schemesSchema = z.array(
  z.object({ name: z.string().nullable(), text: z.string(), selected: z.boolean() }),
);
export type PromptScheme = z.infer<typeof schemesSchema>[number];

export function readPromptSchemes(value: unknown, activeText: string): PromptScheme[] {
  const parsed = schemesSchema.safeParse(value);
  if (parsed.success && parsed.data[0]?.name === null && parsed.data.some((row) => row.selected)) {
    // 宿主的纯文本编辑入口仍可用，选中的方案始终以运行中的正文为准。
    return parsed.data.map((row) => (row.selected ? { ...row, text: activeText } : row));
  }
  return [{ name: null, text: activeText, selected: true }];
}

export function expandAnalysisPrompt(
  template: string,
  variables: Record<string, PromptVariable>,
  config: Readonly<Record<string, unknown>> = {},
) {
  const used = new Set<string>();
  const unknown = new Set<string>();
  const declared = new Map(Object.entries(variables));
  // 对齐 Python string.Template，保留普通花括号、未知变量和不完整的美元符号。
  const expanded = template.replace(
    /\$\$|\$\{([a-zA-Z_][a-zA-Z_0-9]*)\}|\$([a-zA-Z_][a-zA-Z_0-9]*)/g,
    (token: string, braced?: string, bare?: string) => {
      if (token === "$$") return "$";
      const key = braced ?? bare ?? "";
      const variable = declared.get(key);
      if (!variable) {
        unknown.add(key);
        return token;
      }
      used.add(key);
      const configured = variable.config_field ? config[variable.config_field] : undefined;
      return typeof configured === "number" ? String(configured) : variable.example;
    },
  );
  const missing = Object.entries(variables)
    .filter(([key, variable]) => variable.required && !used.has(key))
    .map(([key]) => key);
  return { expanded, missing, unknown: [...unknown], used };
}
