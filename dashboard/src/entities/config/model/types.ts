export interface SchemaFieldItem {
  type: "string" | "int" | "float" | "bool" | "list" | "object";
  description?: string;
  hint?: string;
  default?: unknown;
  options?: Array<string | number>;
  items?: SchemaFieldItem;
  [key: string]: unknown;
}

export interface SchemaGroupItem {
  description: string;
  type: "object";
  hint?: string;
  items: Record<string, SchemaFieldItem>;
  [key: string]: unknown;
}

export type PluginSchema = Record<string, SchemaGroupItem>;

export interface PluginConfigData {
  config: Record<string, Record<string, unknown>>;
  schema: PluginSchema;
}
