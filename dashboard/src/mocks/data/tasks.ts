import type { ActiveTask } from "../../entities/task/model/types";
import type { ConnectedPlatform } from "../../entities/task/api/taskApi";

export const mockConnectedPlatforms: ConnectedPlatform[] = [
  {
    id: "aiocqhttp_main",
    display_name: "QQ (NapCat / OneBot)",
    type: "aiocqhttp",
    label: "QQ 官方/OneBot 实例",
  },
  {
    id: "telegram_main",
    display_name: "Telegram Bot",
    type: "telegram",
    label: "TG 频道与群聊适配器",
  },
  {
    id: "discord_main",
    display_name: "Discord Server",
    type: "discord",
    label: "Discord 社区服务器",
  },
  {
    id: "qq_official_main",
    display_name: "QQ 官方开放平台",
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
    trigger_type: "auto",
    current_stage: "LLM_ANALYSIS",
    started_at: (Date.now() - 42000) / 1000,
    duration_s: 42,
    last_heartbeat: Date.now() / 1000,
  },
  {
    task_id: "task-live-demo-2-just-started",
    group_id: "987654321",
    group_name: "AstrBot 核心测试群",
    platform: "aiocqhttp",
    trigger_type: "manual",
    current_stage: "FETCH_MESSAGES",
    started_at: (Date.now() - 2000) / 1000,
    duration_s: 2,
    last_heartbeat: Date.now() / 1000,
  },
  {
    task_id: "task-live-demo-3-long-name",
    group_id: "8899001122",
    group_name: "🌸 2026 深度学习与自然语言处理前沿学术讨论暨核心内测技术交流特大群 (第 3 分群) 🚀",
    platform: "aiocqhttp",
    trigger_type: "manual",
    current_stage: "RENDER_REPORT",
    started_at: (Date.now() - 75000) / 1000,
    duration_s: 75,
    last_heartbeat: Date.now() / 1000,
  },
  {
    task_id: "task-live-demo-4-long-duration",
    group_id: "-1001987654321",
    group_name: "DevOps & SRE Infra Alert Channel [PROD]",
    platform: "telegram",
    trigger_type: "manual",
    current_stage: "COMIC_DRAWING",
    started_at: (Date.now() - 365000) / 1000,
    duration_s: 365,
    last_heartbeat: Date.now() / 1000,
  },
];
