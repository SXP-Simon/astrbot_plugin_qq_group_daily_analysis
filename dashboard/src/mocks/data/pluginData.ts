import {
  CheckpointsListResponse,
  IncrementalBatchesResponse,
  PluginDataOverview,
} from "../../entities/plugin-data/model/types";

export const mockPluginDataOverview: PluginDataOverview = {
  avatars: { count: 82, size_bytes: 3120000 },
  custom_templates: { count: 3, size_bytes: 2518900 },
  config_files: { count: 6, size_bytes: 620000 },
  config_backups: { count: 5, size_bytes: 210000 },
  reports: { count: 18, size_bytes: 14420000 },
  temp_files: { count: 8, size_bytes: 2400000 },
};

export const mockIncrementalBatches: IncrementalBatchesResponse = {
  group_id: "123456789",
  cursor: {
    group_id: "123456789",
    last_analyzed_timestamp: Date.now() - 86400000,
    last_message_timestamp: Date.now(),
    tracked_message_ids_count: 2450,
  },
  batches: [
    {
      group_id: "123456789",
      batch_id: "batch-20260926-01",
      timestamp: Date.now() - 43200000,
      created_at_iso: "2026-09-26T12:00:05Z",
      messages_count: 420,
      characters_count: 6850,
      topics_count: 3,
      topics: [
        { title: "React 19 特性讨论", summary: "探讨了 Action 与 Server Component 在企业级开发中的应用", heat_score: 88 },
        { title: "LLM Agent 状态机架构", summary: "探讨了断点续跑与快照恢复的设计模式", heat_score: 92 },
      ],
    },
    {
      group_id: "123456789",
      batch_id: "batch-20260926-02",
      timestamp: Date.now() - 21600000,
      created_at_iso: "2026-09-26T18:00:04Z",
      messages_count: 650,
      characters_count: 11200,
      topics_count: 4,
      topics: [
        { title: "TypeScript 5.8 新类型语法", summary: "深入分析了严格空安全与内联优化", heat_score: 80 },
        { title: "群友摸鱼技术交流", summary: "分享了开源键盘与显示器选购心得", heat_score: 75 },
      ],
    },
    {
      group_id: "123456789",
      batch_id: "batch-20260926-03",
      timestamp: Date.now() - 3600000,
      created_at_iso: "2026-09-26T23:00:00Z",
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
      stage_name: "llm_analysis",
      trace_id: "trace-20260926-001",
      data_size_bytes: 5230,
      created_at: Date.now() - 3600000,
      created_at_formatted: "2026-09-26 00:00:14",
      has_data: true,
    },
    {
      checkpoint_id: "chk-20260926-002-dense",
      group_id: "8899001122",
      date_str: "2026-09-26",
      stage_name: "comic_generation",
      trace_id: "trace-20260926-002-dense",
      data_size_bytes: 84000,
      created_at: Date.now() - 7167500,
      created_at_formatted: "2026-09-26 23:02:10",
      has_data: true,
    },
    {
      checkpoint_id: "chk-20260926-004-timeout",
      group_id: "987654321",
      date_str: "2026-09-26",
      stage_name: "llm_analysis",
      trace_id: "trace-20260926-004-timeout",
      data_size_bytes: 3820,
      created_at: Date.now() - 1798800,
      created_at_formatted: "2026-09-26 00:30:02",
      has_data: true,
    },
    {
      checkpoint_id: "chk-20260924-008",
      group_id: "123456789",
      date_str: "2026-09-24",
      stage_name: "report_rendering",
      trace_id: "trace-20260924-008-resumed",
      data_size_bytes: 4100,
      created_at: Date.now() - 259200000,
      created_at_formatted: "2026-09-24 00:00:10",
      has_data: true,
    },
  ],
};
