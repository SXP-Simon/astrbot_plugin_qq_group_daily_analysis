/**
 * 配置项选项的显示名（官方键 `labels`）。
 *
 * schema 里 `options` 存的是配置真实值（如 `zh-Hans`），`labels` 是**与 options 顺序一一对应**
 * 的显示名数组（官方能力，支持按 WebUI 语言切换）。本函数按位置取标签：位置对不上、
 * 标签缺失或为空时回退显示原始值，避免串位后静默显示错标签。
 */
export function resolveOptionLabel(
  raw: string,
  options: unknown[] | undefined,
  labels: string[] | undefined,
): string {
  if (!Array.isArray(options) || !Array.isArray(labels)) return raw;
  const index = options.findIndex((option) => String(option) === raw);
  if (index < 0) return raw;
  const label = labels[index];
  return label && label.trim() ? label : raw;
}
