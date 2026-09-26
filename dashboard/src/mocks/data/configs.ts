import { PluginConfigData } from "../../entities/config/model/types";
import { AvailablePersona, AvailableProvider } from "../../entities/config/api/configApi";

export const mockPluginConfig: PluginConfigData = {
  config: {
    general: {
      analysis_time: "00:00",
      max_history_days: 7,
      auto_daily_analysis: true,
      llm_provider: "deepseek-chat",
      report_template: "scrapbook",
      enable_runtime_metrics: true,
    },
    llm_advanced: {
      temperature: 0.7,
      max_tokens: 4096,
      persona: "default",
      timeout_seconds: 30,
      enable_streaming: false,
    },
    comic: {
      enable_comic: true,
      comic_engine: "dall-e-3",
      comic_panels: 4,
      comic_style: "japanese_manga",
    },
    filter_rules: {
      ignore_bots: true,
      min_message_count: 10,
      filter_system_messages: true,
    },
    storage: {
      enable_wal: true,
      checkpoint_retention_days: 3,
      auto_clean_temp_files: true,
    },
  },
  schema: {
    general: {
      description: "群分析基础调度配置",
      type: "object",
      items: {
        analysis_time: {
          type: "string",
          description: "每日定时分析触发时间 (HH:MM)",
          default: "00:00",
        },
        auto_daily_analysis: {
          type: "bool",
          description: "开启定时每日总结",
          default: true,
        },
        llm_provider: {
          type: "string",
          description: "选择用于分析聊天总结的 LLM 模型服务",
        },
        report_template: {
          type: "string",
          description: "生成日报海报时使用的主题模板",
        },
        max_history_days: {
          type: "int",
          description: "最大聊天记录回溯天数",
          default: 7,
        },
        enable_runtime_metrics: {
          type: "bool",
          description: "开启运行时链路与 Token 耗时监控",
          default: true,
        },
      },
    },
    llm_advanced: {
      description: "大模型高级推理与人格配置",
      type: "object",
      items: {
        temperature: {
          type: "float",
          description: "大模型生成发散度 (0.0 ~ 1.0)",
          default: 0.7,
        },
        max_tokens: {
          type: "int",
          description: "单次总结最大输出 Token 数量",
          default: 4096,
        },
        persona: {
          type: "string",
          description: "分析官语气人格风格",
          default: "default",
        },
        timeout_seconds: {
          type: "int",
          description: "API 网络调用超时时间 (秒)",
          default: 30,
        },
        enable_streaming: {
          type: "bool",
          description: "启用流式响应分析",
          default: false,
        },
      },
    },
    comic: {
      description: "群漫画与多模态生图配置",
      type: "object",
      items: {
        enable_comic: {
          type: "bool",
          description: "在每日总结中开启群漫画生成",
          default: false,
        },
        comic_engine: {
          type: "string",
          description: "漫画生成图像模型引擎",
          default: "dall-e-3",
        },
        comic_panels: {
          type: "int",
          description: "漫画分镜格数 (4格/6格)",
          default: 4,
        },
        comic_style: {
          type: "string",
          description: "漫画艺术风格",
          default: "japanese_manga",
        },
      },
    },
    filter_rules: {
      description: "消息清洗与过滤规则",
      type: "object",
      items: {
        ignore_bots: {
          type: "bool",
          description: "自动忽略其他机器人的发言",
          default: true,
        },
        min_message_count: {
          type: "int",
          description: "触发分析的最低有效发言数阈值",
          default: 10,
        },
        filter_system_messages: {
          type: "bool",
          description: "过滤撤回、戳一戳等系统消息",
          default: true,
        },
      },
    },
    storage: {
      description: "持久化存储与缓存管理",
      type: "object",
      items: {
        enable_wal: {
          type: "bool",
          description: "开启 SQLite WAL 高性能并发模式",
          default: true,
        },
        checkpoint_retention_days: {
          type: "int",
          description: "断点续跑快照保留天数",
          default: 3,
        },
        auto_clean_temp_files: {
          type: "bool",
          description: "分析完成后自动清理渲染临时中间文件",
          default: true,
        },
      },
    },
  },
};

export const mockProviders: AvailableProvider[] = [
  { id: "deepseek-chat", name: "DeepSeek Chat (V3)", type: "openai_compatible", label: "DeepSeek Official" },
  { id: "openai", name: "OpenAI GPT-4o", type: "openai", label: "OpenAI Main" },
  { id: "claude-3-5-sonnet", name: "Claude 3.5 Sonnet", type: "anthropic", label: "Anthropic Direct" },
  { id: "ollama_local", name: "Ollama (Local Qwen2.5-7B)", type: "openai_compatible", label: "Local Private" },
];

export const mockPersonas: AvailablePersona[] = [
  { id: "default", name: "标准毒舌总结官", label: "语气幽默锐利、一针见血提炼群热点" },
  { id: "cute_maid", name: "贴心女仆看板娘", label: "温柔软萌、善解人意、鼓励群友活跃" },
  { id: "academic_scholar", name: "严谨学术研究员", label: "客观中立、条理清晰、结构化要点提炼" },
  { id: "cyber_hacker", name: "赛博极客观察者", label: "科技感、暗黑极客风、冷峻幽默" },
];
