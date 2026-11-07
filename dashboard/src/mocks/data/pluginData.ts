import {
  CheckpointsListResponse,
  IncrementalBatchesResponse,
  PluginDataOverview,
} from "../../entities/plugin-data/model/types";

export const mockPluginDataOverview: PluginDataOverview = {
  avatars: { count: 82, size_bytes: 3120000 },
  custom_templates: { count: 3, size_bytes: 2518900 },
  config_files: { count: 6, size_bytes: 620000 },
  config_backups: { count: 3, size_bytes: 19794 },
  reports: { count: 18, size_bytes: 14420000 },
  temp_files: { count: 8, size_bytes: 2400000 },
};

const incrementalNow = Math.floor(Date.now() / 1000);

export const mockIncrementalBatches: IncrementalBatchesResponse = {
  group_id: "123456789",
  cursor: {
    timestamp: incrementalNow - 86400,
    group_id: "123456789",
    last_analyzed_timestamp: incrementalNow - 86400,
    last_message_timestamp: incrementalNow,
    tracked_message_ids_count: 2450,
  },
  batches: [
    {
      group_id: "123456789",
      batch_id: "batch-20260926-01",
      timestamp: incrementalNow - 43200,
      created_at_iso: new Date((incrementalNow - 43200) * 1000).toISOString(),
      messages_count: 420,
      characters_count: 6850,
      topics_count: 2,
      last_message_timestamp: incrementalNow - 43260,
      token_usage: { total_tokens: 3600, prompt_tokens: 2800, completion_tokens: 800 },
      chat_quality_review: {
        title: "示例：技术交流与轻松闲聊",
        subtitle: "讨论集中，气氛友好",
        summary: "大家围绕实际开发问题分享经验，偶尔穿插日常话题。",
        dimensions: [{ name: "信息交流", percentage: 75, comment: "问题和解答都有具体背景。" }],
      },
      golden_quotes_count: 1,
      golden_quotes: [
        { content: "先把问题复现出来，修复就有了方向。", sender_nickname: "示例小林" },
      ],
      topics: [
        {
          title: "React 19 特性讨论",
          summary: "探讨了 Action 与 Server Component 在企业级开发中的应用",
          heat_score: 88,
        },
        {
          title: "LLM Agent 状态机架构",
          summary: "探讨了断点续跑与快照恢复的设计模式",
          heat_score: 92,
        },
      ],
    },
    {
      group_id: "123456789",
      batch_id: "batch-20260926-02",
      timestamp: incrementalNow - 21600,
      created_at_iso: new Date((incrementalNow - 21600) * 1000).toISOString(),
      messages_count: 650,
      characters_count: 11200,
      topics_count: 4,
      topics: [
        {
          title: "TypeScript 5.8 新类型语法",
          summary: "深入分析了严格空安全与内联优化",
          heat_score: 80,
        },
        { title: "群友摸鱼技术交流", summary: "分享了开源键盘与显示器选购心得", heat_score: 75 },
      ],
    },
    {
      group_id: "123456789",
      batch_id: "batch-20260926-03",
      timestamp: incrementalNow - 3600,
      created_at_iso: new Date((incrementalNow - 3600) * 1000).toISOString(),
      messages_count: 470,
      characters_count: 8900,
      topics_count: 2,
    },
  ],
};

export const mockCheckpoints: CheckpointsListResponse = {
  total: 4,
  items: [
    {
      checkpoint_id: "chk-20260926-001",
      group_id: "123456789",
      date_str: "2026-09-26",
      stage_name: "LLM_ANALYSIS",
      trace_id: "trace-20260926-001",
      data_size_bytes: 5230,
      created_at: Math.floor((Date.now() - 3600000) / 1000),
      has_data: true,
    },
    {
      checkpoint_id: "chk-20260926-002-dense",
      group_id: "8899001122",
      date_str: "2026-09-26",
      stage_name: "COMIC_DRAWING",
      trace_id: "trace-20260926-002-dense",
      data_size_bytes: 84000,
      created_at: Math.floor((Date.now() - 7167500) / 1000),
      has_data: true,
    },
    {
      checkpoint_id: "chk-20260926-004-timeout",
      group_id: "987654321",
      date_str: "2026-09-26",
      stage_name: "LLM_ANALYSIS",
      trace_id: "trace-20260926-004-timeout",
      data_size_bytes: 3820,
      created_at: Math.floor((Date.now() - 1798800) / 1000),
      has_data: true,
    },
    {
      checkpoint_id: "chk-20260924-008",
      group_id: "123456789",
      date_str: "2026-09-24",
      stage_name: "RENDER_REPORT",
      trace_id: "trace-20260924-008-resumed",
      data_size_bytes: 4100,
      created_at: Math.floor((Date.now() - 259200000) / 1000),
      has_data: true,
    },
  ],
};

for (const item of [...mockCheckpoints.items]) {
  for (const stage of [
    "FETCH_MESSAGES",
    "CLEAN_MESSAGES",
    "STATS_ANALYSIS",
    "LLM_ANALYSIS",
    "RENDER_REPORT",
    "COMIC_DRAWING",
  ]) {
    if (stage === item.stage_name) continue;
    if (item.trace_id?.includes("timeout") && ["RENDER_REPORT", "COMIC_DRAWING"].includes(stage))
      continue;
    mockCheckpoints.items.push({
      ...item,
      checkpoint_id: `${item.checkpoint_id}-${stage}`,
      stage_name: stage,
    });
  }
}
mockCheckpoints.items.push({
  checkpoint_id: "demo-daily-checkpoint",
  group_id: "123456789",
  date_str: "2026-09-23",
  stage_name: "LLM_ANALYSIS",
  trace_id: "",
  data_size_bytes: 0,
  created_at: Math.floor(Date.now() / 1000) - 86400,
});
mockCheckpoints.total = mockCheckpoints.items.length;
