import { describe, expect, it } from "vitest";
import { DEFAULT_WORDCLOUD_OPTIONS } from "../../../../entities/wordcloud/model/types";
import { DENSITY_PRESETS, fitCandidates, readableDraft, visualPatch } from "../wordCloudLayout";

describe("词云外观批量调整", () => {
  it("预设和恢复模板默认只包含外观，保留发送、词频和扩展配置", () => {
    const patch = visualPatch({ ...DEFAULT_WORDCLOUD_OPTIONS, enabled: false, min_frequency: 8, group_overrides: { group: {} }, future: true });
    expect(patch).toHaveProperty("font", "wenkai");
    expect(patch).not.toHaveProperty("enabled");
    expect(patch).not.toHaveProperty("min_frequency");
    expect(patch).not.toHaveProperty("group_overrides");
    expect(patch).not.toHaveProperty("future");
    expect(Object.keys(DENSITY_PRESETS.compact).sort()).toEqual(["max_font_size", "max_words", "min_font_size", "word_spacing"]);
  });

  it("单项错误不重置其他字段，越界数值与倒置字号原样显示", () => {
    expect(readableDraft({ word_spacing: 60, min_font_size: 110, max_font_size: 80, font: "uploaded:test.woff2", width: 1500 })).toMatchObject({
      word_spacing: 60, min_font_size: 110, max_font_size: 80, font: "uploaded:test.woff2", width: 1500,
    });
  });

  it("自动紧凑调整有四轮上限且不修改词数、画布和统计规则", () => {
    const initial = { ...DEFAULT_WORDCLOUD_OPTIONS, width: 1800, max_words: 160, min_frequency: 6 };
    const candidates = fitCandidates(initial);
    expect(candidates).toHaveLength(4);
    expect(candidates[0]).toMatchObject({ word_spacing: 5, min_font_size: 34, max_font_size: 90 });
    for (const candidate of candidates) {
      expect(candidate).toMatchObject({ width: 1800, max_words: 160, min_frequency: 6 });
      expect(candidate.min_font_size).toBeGreaterThanOrEqual(Math.floor(initial.min_font_size * 0.75));
      expect(candidate.max_font_size).toBeGreaterThanOrEqual(Math.floor(initial.max_font_size * 0.75));
    }
    expect(fitCandidates({ ...initial, word_spacing: 0, min_font_size: 12, max_font_size: 12 })).toEqual([]);
  });
});
