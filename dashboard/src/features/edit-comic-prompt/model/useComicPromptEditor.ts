import catalog from "../../../../../src/shared/comic_prompt_templates.json";

export interface ComicPromptTemplate {
  id: string;
  name: string;
  description: string;
  prompt: string;
  preview?: string;
}

export const comicPromptTemplates: ComicPromptTemplate[] = Object.entries(catalog).map(([id, entry]) => ({
  id,
  ...entry,
}));

/** 内置模板与自定义草稿分开保存，切换选项不会覆盖草稿。 */
export function useComicPromptEditor(value: unknown, onChange: (value: unknown) => void) {
  const config = typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
  const preset = comicPromptTemplates.find(({ id }) => id === config.comic_storyboard_template);
  const selection = preset?.id ?? "custom";
  const custom = typeof config.comic_storyboard_prompt === "string"
    ? config.comic_storyboard_prompt
    : catalog.classic.prompt;

  return {
    selection,
    custom,
    preset,
    selectTemplate: (id: string) => onChange({ ...config, comic_storyboard_template: id }),
    editCustom: (prompt: string) => onChange({ ...config, comic_storyboard_prompt: prompt }),
    copyPreset: () => {
      if (!preset) return;
      onChange({ ...config, comic_storyboard_template: "custom", comic_storyboard_prompt: preset.prompt });
    },
  };
}
