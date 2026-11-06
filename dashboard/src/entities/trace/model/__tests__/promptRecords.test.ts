import { expect, it } from "vitest";
import { getPromptGroups } from "../promptRecords";

it("保留历史字符串、未知模块和含 retry 或井号的正常模块", () => {
  const groups = getPromptGroups({
    topics: "示例提示词",
    retry_planner: "计划",
    "绘图#1": { completion: "图片描述" },
  });
  expect(groups.map((group) => group.key)).toEqual(["topics", "retry_planner", "绘图#1"]);
  expect(groups[0].records[0].detail.prompt).toBe("示例提示词");
});

it("模块名与对象原型属性同名时仍按原名显示", () => {
  const [group] = getPromptGroups({ constructor: "正常记录", toString: "文本" });
  expect(group.label).toBe("constructor");
});

it("保留全部重试并按次数排列，已知中文别名归入对应模块", () => {
  const groups = getPromptGroups({
    topics: { prompt: "初始", completion: "首次返回" },
    "话题分析#schema_retry_10": { prompt: "修复十", completion: "仍未解析" },
    "话题#schema_retry_2": { prompt: "修复二", completion: "第二次返回" },
    "topics#retry_1": { provider_id: "backup" },
  });
  expect(groups).toHaveLength(1);
  expect(groups[0].records.map((record) => record.label)).toEqual([
    "模块记录",
    "重试第 1 次",
    "格式修复第 2 次",
    "格式修复第 10 次",
  ]);
  expect(groups[0].records[1].detail).toEqual({ provider_id: "backup" });
});

it("初始与校正记录不混用正文，不将汇总 Token 和模型复制给初始请求", () => {
  const [group] = getPromptGroups({
    topics: {
      initial_prompt: "",
      initial_completion: "坏格式",
      corrected_prompt: "修复",
      corrected_completion: "[]",
      tokens: 200,
      provider_id: "最终模型",
      retry_count: 2,
    },
    "topics#schema_retry_1": { completion: "另一次坏格式" },
  });
  expect(group.records.map((record) => record.label)).toEqual([
    "初始记录",
    "格式修复第 1 次",
    "校正记录",
  ]);
  expect(group.records[0].detail).toMatchObject({ prompt: "", completion: "坏格式" });
  expect(group.records[0].detail.tokens).toBeUndefined();
  expect(group.records[0].detail.provider_id).toBeUndefined();
  expect(group.records[2].detail).toMatchObject({ prompt: "修复", completion: "[]", tokens: 200 });
});

it("孤立重试和有歧义的别名不消失，也不错误合并", () => {
  const groups = getPromptGroups({
    topics: "英文键",
    话题分析: "中文键",
    "话题#retry_1": "单独查看",
    "comic#retry_3": "漫画记录",
  });
  expect(groups).toHaveLength(4);
  expect(groups[2].records[0].detail.prompt).toBe("单独查看");
  expect(groups[3].label).toBe("群漫画");
});

it("异常字段单独忽略，空文本和真实零值保留，坏条目仍可定位", () => {
  expect(getPromptGroups(null)).toEqual([]);
  expect(getPromptGroups(["不属于模块映射"])).toEqual([]);
  const groups = getPromptGroups({
    topics: {
      prompt: {},
      completion: "",
      tokens: 0,
      prompt_tokens: -1,
      completion_tokens: Infinity,
    },
    broken: null,
  });
  expect(groups[0].records[0].detail).toMatchObject({ completion: "", tokens: 0 });
  expect(groups[0].records[0].detail.prompt).toBeUndefined();
  expect(groups[0].records[0].detail.prompt_tokens).toBeUndefined();
  expect(groups[1].records[0].malformed).toBe(true);
});
