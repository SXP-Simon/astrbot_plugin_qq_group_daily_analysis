import { describe, expect, it } from "vitest";

import { resolveOptionLabel } from "../optionLabel";

const OPTIONS = ["auto", "zh-Hans", "zh-Hant", "en", "ja"];
const LABELS = ["自动（按群聊判断）", "简体中文", "繁體中文", "ENGLISH", "日本語"];

describe("resolveOptionLabel（官方键 labels，位置对应）", () => {
  it("按位置取标签（配置值仍是 options 里的原始值）", () => {
    expect(resolveOptionLabel("zh-Hans", OPTIONS, LABELS)).toBe("简体中文");
    expect(resolveOptionLabel("ja", OPTIONS, LABELS)).toBe("日本語");
    expect(resolveOptionLabel("auto", OPTIONS, LABELS)).toBe("自动（按群聊判断）");
  });

  it("顺序错位会显示错标签 —— 因此 schema 侧由测试兜底防串位", () => {
    // 故意把 labels 顺序打乱，验证「位置对应」这一语义确实成立（不是按值索引）
    const wrong = ["简体中文", "自动（按群聊判断）", "繁體中文", "ENGLISH", "日本語"];
    expect(resolveOptionLabel("auto", OPTIONS, wrong)).toBe("简体中文");
  });

  it("标签数量与 options 不一致时，缺位回退原始值", () => {
    const short = ["自动（按群聊判断）", "简体中文"];
    expect(resolveOptionLabel("zh-Hans", OPTIONS, short)).toBe("简体中文");
    expect(resolveOptionLabel("ja", OPTIONS, short)).toBe("ja");
  });

  it("选项值不在 options 里、标签为空、或整份缺失时回退原始值", () => {
    expect(resolveOptionLabel("zh-Hant", ["auto"], ["自动"])).toBe("zh-Hant");
    expect(resolveOptionLabel("en", OPTIONS, ["", "", "", "   ", ""])).toBe("en");
    expect(resolveOptionLabel("auto", OPTIONS, undefined)).toBe("auto");
    expect(resolveOptionLabel("auto", undefined, LABELS)).toBe("auto");
  });
});
