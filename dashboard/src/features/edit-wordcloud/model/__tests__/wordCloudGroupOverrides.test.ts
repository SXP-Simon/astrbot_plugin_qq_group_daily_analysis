import { describe, expect, it } from "vitest";
import { buildOverrideGroupOptions, getEffectiveWordCloud, getOverrideErrors, isGroupUmo, setOverrideFields, updateGroupOverride } from "../wordCloudGroupOverrides";

const umo = "bot:GroupMessage:123456";

describe("词云群级覆盖", () => {
  it("按完整会话区分同群号的不同平台，并保留已离线群", () => {
    const options = buildOverrideGroupOptions([
      { group_id: "123456", group_name: "群甲", platform: "bot" },
      { group_id: "123456", group_name: "群乙", platform: "other" },
      { group_id: "999", group_name: "缺少平台", platform: "auto" },
    ], { [umo]: { word_spacing: 4 }, "offline:GroupMessage:222": { enabled: false } });
    expect(options.map((option) => option.value)).toEqual([umo, "other:GroupMessage:123456", "offline:GroupMessage:222"]);
    expect(options[0].label).toContain("群甲");
  });

  it("仅接受完整群会话标识，允许非数字群号", () => {
    expect(isGroupUmo(umo)).toBe(true);
    expect(isGroupUmo("bot:GroupMessage:guild:channel")).toBe(true);
    expect(isGroupUmo("123456")).toBe(false);
    expect(isGroupUmo("bot:FriendMessage:123456")).toBe(false);
    expect(isGroupUmo("bot:GroupMessage:123 456")).toBe(false);
  });

  it("只合并被覆盖字段，未覆盖字段跟随全局变化", () => {
    expect(getEffectiveWordCloud({ font: "serif", word_spacing: 8 }, { word_spacing: 2 })).toMatchObject({ font: "serif", word_spacing: 2, width: 1200 });
    expect(getEffectiveWordCloud({ font: "sans", group_overrides: { [umo]: {} } }, { word_spacing: 2 })).toMatchObject({ font: "sans", word_spacing: 2 });
    expect(getEffectiveWordCloud({ group_overrides: {} }, {})).not.toHaveProperty("group_overrides");
  });

  it("新增覆盖复制当前全局值，保留已有值、未知字段与其他群", () => {
    const before = { [umo]: { word_spacing: 2, future_option: { enabled: true }, group_name: "我的群" }, "other:GroupMessage:123": { font: "serif" } };
    const after = setOverrideFields(before, umo, ["word_spacing", "font"], { word_spacing: 10, font: "uploaded:custom.woff2" });
    expect(after[umo]).toEqual({ word_spacing: 2, font: "uploaded:custom.woff2", future_option: { enabled: true }, group_name: "我的群" });
    expect(after["other:GroupMessage:123"]).toBe(before["other:GroupMessage:123"]);
    expect(before[umo]).not.toHaveProperty("font");
  });

  it("恢复继承只移除受支持字段，保留群元数据", () => {
    const before = { [umo]: { font: "sans", word_spacing: 4, group_name: "备注", future_option: 10 } };
    expect(setOverrideFields(before, umo, [], {})).toEqual({ [umo]: { group_name: "备注", future_option: 10 } });
    expect(setOverrideFields({ [umo]: { font: "sans" } }, umo, [], {})).toEqual({});
  });

  it("单项修改以一次回调所需的完整覆盖对象返回且不改变源对象", () => {
    const before = { [umo]: { font: "sans", future_option: 7 }, "other:GroupMessage:123": { enabled: false } };
    const after = updateGroupOverride(before, umo, "font", "serif");
    expect(after).toEqual({ [umo]: { font: "serif", future_option: 7 }, "other:GroupMessage:123": { enabled: false } });
    expect(before[umo].font).toBe("sans");
  });

  it("错误格式的旧群覆盖不因操作被清空", () => {
    const before = { [umo]: "invalid legacy value" };
    expect(setOverrideFields(before, umo, ["font"], {})).toBe(before);
    expect(updateGroupOverride(before, umo, "font", "sans")).toBe(before);
  });

  it("校验继承后的字号关系和配色，不用默认值掩盖出错草稿", () => {
    const errors = getOverrideErrors({ max_font_size: 60, font: "uploaded:old.woff2" }, { min_font_size: 90, palette: ["wrong"] });
    expect(errors).toHaveProperty("palette");
    expect(getOverrideErrors({ max_font_size: 60 }, { min_font_size: 90 })).toHaveProperty("min_font_size");
    const effective = getEffectiveWordCloud({ font: "uploaded:old.woff2" }, { min_font_size: 900 });
    expect(effective.font).toBe("uploaded:old.woff2");
    expect(effective.min_font_size).toBe(900);
  });
});
