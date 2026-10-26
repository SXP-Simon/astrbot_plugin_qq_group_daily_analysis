import type { ConfigBackupDetail } from "../../entities/plugin-data/model/configBackup";

export const mockConfigBackups: ConfigBackupDetail[] = [
  {
    backup: {
      filename: "plugin_config_v5.8.3_20261025_213000.json",
      size_bytes: 18420,
      kind: "upgrade",
      plugin_version: "v5.8.3",
      saved_at: "2026-10-25T21:30:00",
      error: null,
    },
    content: {
      plugin_version: "v5.8.3",
      backed_up_at: "2026-10-25T21:30:00",
      config: {
        basic: {
          report_template: "HatsuneMiku",
          max_topics: 8,
          enable_notifications: true,
        },
        t2i_rendering: {
          t2i_mainland_cdn_base_url: "https://cdn.example.com",
          t2i_mainland_google_fonts: "https://fonts.example.com",
          t2i_rendering_strategies: [
            { name: "旧版内地方案", environment: "Mainland", timeout: 20000 },
          ],
        },
        prompts: {
          topic_analysis:
            "请根据群聊消息整理当天的话题。\n保留参与者的主要观点，并说明讨论的结果。\n如果消息不足，可以返回空列表。",
        },
        removed_group: {
          example_array: ["原始文本", 42, false, null],
          nested: { unknown_key: "旧版本字段也能展开查看" },
        },
      },
    },
  },
  {
    backup: {
      filename: "comic_character_migration_20261024_083000.json",
      size_bytes: 1024,
      kind: "comic_migration",
      plugin_version: null,
      saved_at: "2026-10-24T08:30:00",
      error: null,
    },
    content: {
      migrated_at: "2026-10-24T08:30:00",
      config: {
        drawing_reference_image: ["https://example.com/character.png"],
        comic_characters: [{ name: "旧角色", enabled: true }],
      },
    },
  },
  {
    backup: {
      filename: "legacy_config.json",
      size_bytes: 350,
      kind: "other",
      plugin_version: null,
      saved_at: null,
      error: null,
    },
    content: {
      previous_options: {
        values: [1, false, null],
        empty: {},
        notes: "这份旧文件没有记录版本和时间。",
      },
    },
  },
];
