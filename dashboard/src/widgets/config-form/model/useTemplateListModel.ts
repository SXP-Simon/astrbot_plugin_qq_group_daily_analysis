import type { SchemaFieldItem } from "../../../entities/config/model/types";

export function useTemplateListModel(
  schema: SchemaFieldItem,
  value: unknown,
  onChange: (value: unknown) => void,
) {
  const source: unknown = value ?? schema.default ?? [];
  const valid =
    Array.isArray(source) &&
    source.every(
      (item: unknown) => item !== null && typeof item === "object" && !Array.isArray(item),
    );
  const items: Record<string, unknown>[] = valid ? source : [];
  const templates = schema.templates ?? {};
  const templateKeys = Object.keys(templates);

  const templateKey = (item: Record<string, unknown>): string | undefined => {
    if (typeof item.__template_key === "string" && templates[item.__template_key])
      return item.__template_key;
    if (typeof item.name === "string" && templates[item.name]) return item.name;
    return templateKeys.find((key) => templates[key].name === item.name) ?? templateKeys[0];
  };
  const normalized = () =>
    items.map((item) => ({ ...item, __template_key: templateKey(item) ?? "character" }));

  const add = (key: string) => {
    const template = templates[key];
    if (!valid || !template) return;
    const item: Record<string, unknown> = { __template_key: key, name: template.name ?? key };
    for (const [field, definition] of Object.entries(template.items ?? {})) {
      if (definition.default !== undefined) item[field] = structuredClone(definition.default);
    }
    onChange([...normalized(), item]);
  };
  const change = (index: number, field: string, value: unknown) => {
    if (!valid || !items[index]) return;
    onChange(normalized().map((item, i) => (i === index ? { ...item, [field]: value } : item)));
  };
  const remove = (index: number) => {
    if (!valid || !items[index]) return;
    onChange(normalized().filter((_, i) => i !== index));
  };
  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (!valid || !items[index] || !items[target]) return;
    const next = normalized();
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };
  return { items, valid, templates, templateKeys, templateKey, add, change, remove, move };
}
