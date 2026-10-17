import { describe, expect, it } from "vitest";
import { pluginConfigSaveSchema } from "../configContract";
import { validateConfigWithZod } from "../validation";
import type { PluginSchema } from "../types";

const schema: PluginSchema = { daily_comic: { type: "object", description: "每日漫画", items: {
  comic_template_mode: { type: "string", options: ["fixed", "sequential", "daily_sequential", "random", "daily_random", "shuffle"] },
  comic_template_scope: { type: "string", options: ["global", "group"] },
  comic_template_candidates: { type: "list", options: ["classic", "pixel_rpg", "custom"] },
} } };

describe("漫画切换草稿保存契约", () => {
  it("旧配置原样兼容，保存顺序和其他字段不变，自定义只在主动加入时参与", () => {
    const config = { daily_comic: { comic_template_mode: "sequential", comic_template_scope: "group", comic_template_candidates: ["pixel_rpg", "classic"], future: 42 }, prompts: { comic_analysis_prompts: { comic_storyboard_template: "custom", comic_storyboard_prompt: "自己的提示词" } } };
    expect(pluginConfigSaveSchema.parse(config)).toEqual(config);
    expect(pluginConfigSaveSchema.parse({ daily_comic: { enable_daily_comic: true } })).toEqual({ daily_comic: { enable_daily_comic: true } });
    expect(validateConfigWithZod(config, schema).isValid).toBe(true);
  });

  it("固定模式允许空候选，自动模式拒绝空候选、重复和未知模板", () => {
    expect(pluginConfigSaveSchema.safeParse({ daily_comic: { comic_template_mode: "fixed", comic_template_candidates: [] } }).success).toBe(true);
    for (const candidates of [[], ["classic", "classic"], ["unknown"]]) {
      const config = { daily_comic: { comic_template_mode: "sequential", comic_template_candidates: candidates } };
      expect(pluginConfigSaveSchema.safeParse(config).success).toBe(false);
      expect(validateConfigWithZod(config, schema).errorMap.daily_comic.comic_template_candidates).toBeTruthy();
    }
  });

  it("包含自定义候选时关联校验提示词文本，补齐即可保存", () => {
    const config = { daily_comic: { comic_template_mode: "random", comic_template_candidates: ["custom"] }, prompts: { comic_analysis_prompts: { comic_storyboard_prompt: "  " } } };
    expect(pluginConfigSaveSchema.safeParse(config).success).toBe(false);
    expect(validateConfigWithZod(config, schema).errorMap.daily_comic.comic_template_candidates).toContain("自定义");
    config.prompts.comic_analysis_prompts.comic_storyboard_prompt = "${chat_content}";
    expect(pluginConfigSaveSchema.safeParse(config).success).toBe(true);
    expect(validateConfigWithZod(config, schema).isValid).toBe(true);
  });
});
