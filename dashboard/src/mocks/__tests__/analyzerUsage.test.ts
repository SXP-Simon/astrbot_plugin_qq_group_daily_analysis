import { expect, it } from "vitest";
import { mockTraces } from "@/mocks/data/traces";

it("模型用量示例沿用实际分析模块标识并保留输入输出记录", () => {
  const names = new Set([
    "topics",
    "user_titles",
    "golden_quotes",
    "chat_quality",
    "comic_storyboard",
  ]);
  for (const trace of mockTraces) {
    for (const [name, usage] of Object.entries(trace.token_usage?.per_analyzer ?? {})) {
      expect(names.has(name), `${trace.trace_id} 的模块 ${name}`).toBe(true);
      expect(usage.total_tokens).toBe(usage.prompt_tokens + usage.completion_tokens);
    }
  }
  expect(
    mockTraces.find((trace) => trace.trace_id === "trace-20260926-001")?.token_usage?.per_analyzer,
  ).toHaveProperty("topics", { prompt_tokens: 1800, completion_tokens: 420, total_tokens: 2220 });
});
