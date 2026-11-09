import catalog from "../../../../../src/shared/comic_prompt_templates.json";

export const comicPresets = Object.entries(catalog).map(([id, item]) => ({ id, ...item }));

export function comicPreviewLabel(path: string): string {
  const [id, filename] = path.split("/");
  const style = comicPresets.find((item) => item.id === id);
  if (!style || !filename) return path;
  return `${style.name} · ${filename.startsWith("thumbnail-") ? "缩略图" : "完整图"}`;
}
