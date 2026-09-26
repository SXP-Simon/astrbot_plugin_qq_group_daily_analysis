import type { ActiveTask } from "../../entities/task/model/types";
import type { ConnectedPlatform } from "../../entities/task/api/taskApi";

export const mockConnectedPlatforms: ConnectedPlatform[] = [
  {
    id: "aiocqhttp_main",
    name: "QQ (NapCat / OneBot)",
    type: "aiocqhttp",
    label: "QQ 官方/OneBot 实例",
  },
  {
    id: "telegram_main",
    name: "Telegram Bot",
    type: "telegram",
    label: "TG 频道与群聊适配器",
  },
  {
    id: "discord_main",
    name: "Discord Server",
    type: "discord",
    label: "Discord 社区服务器",
  },
  {
    id: "qq_official_main",
    name: "QQ 官方开放平台",
    type: "qq_official",
    label: "QQ 官方机器人原生实例",
  },
];

export const mockActiveTasks: ActiveTask[] = [
  {
    task_id: "task-live-demo-1",
    group_id: "123456789",
    group_name: "技术交流与闲聊吹水群",
    platform: "aiocqhttp",
    trigger_type: "cron",
    current_stage: "llm_analysis",
    started_at: Date.now() - 42000,
    duration_s: 42,
    last_heartbeat: Date.now(),
  },
  {
    task_id: "task-live-demo-2-just-started",
    group_id: "987654321",
    group_name: "AstrBot 核心测试群",
    platform: "aiocqhttp",
    trigger_type: "manual",
    current_stage: "data_fetching",
    started_at: Date.now() - 2000,
    duration_s: 2,
    last_heartbeat: Date.now(),
  },
  {
    task_id: "task-live-demo-3-long-name",
    group_id: "8899001122",
    group_name: "🌸 2026 深度学习与自然语言处理前沿学术讨论暨核心内测技术交流特大群 (第 3 分群) 🚀",
    platform: "aiocqhttp",
    trigger_type: "manual",
    current_stage: "report_rendering",
    started_at: Date.now() - 75000,
    duration_s: 75,
    last_heartbeat: Date.now(),
  },
  {
    task_id: "task-live-demo-4-long-duration",
    group_id: "-1001987654321",
    group_name: "DevOps & SRE Infra Alert Channel [PROD]",
    platform: "telegram",
    trigger_type: "manual",
    current_stage: "comic_generation",
    started_at: Date.now() - 365000,
    duration_s: 365,
    last_heartbeat: Date.now(),
  },
];
