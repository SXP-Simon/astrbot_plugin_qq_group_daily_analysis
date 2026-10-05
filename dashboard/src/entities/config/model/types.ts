export type SchemaFieldType =
  | "string"
  | "int"
  | "float"
  | "bool"
  | "list"
  | "object"
  | "template_list"
  | "text"
  | "file"
  | string;

export interface SchemaFieldItem {
  type: SchemaFieldType;
  description?: string;
  hint?: string;
  default?: unknown;
  options?: Array<string | number>;
  /**
   * 选项显示名：与 `options` **顺序一一对应**的数组（官方键，AstrBot 支持按 WebUI 语言切换）。
   * 只影响显示，配置里存的仍是 `options` 里的原始值。
   */
  labels?: string[];
  /**
   * 条件显示（官方键）：依赖项的当前值等于给定值时本字段才显示。
   * 值为单值（与维护者在 `size`/`custom_size` 上的用法一致）；为兼容旧写法也接受数组（命中任一即显示）。
   */
  condition?: Record<string, unknown>;
  items?: SchemaFieldItem | Record<string, SchemaFieldItem>;
  templates?: Record<
    string,
    {
      name?: string;
      description?: string;
      display_item?: string;
      items?: Record<string, SchemaFieldItem>;
    }
  >;
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
