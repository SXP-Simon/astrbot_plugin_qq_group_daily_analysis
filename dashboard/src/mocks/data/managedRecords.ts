import { recordKey } from "../../entities/plugin-data/model/managedRecord";
import type {
  ManagedRecord,
  RecordLocator,
} from "../../entities/plugin-data/api/managedRecordsApi";
import { mockCheckpoints, mockIncrementalBatches, incrementalMockSession } from "./pluginData";

let version = 0;
const records = new Map<string, ManagedRecord>();
function put(locator: RecordLocator, data: ManagedRecord["data"]) {
  const record = { locator, data, revision: `demo-${++version}` };
  records.set(recordKey(locator), record);
  return record;
}
for (const batch of mockIncrementalBatches.batches) {
  put(
    { kind: "batch", platform_id: "aiocqhttp", group_id: batch.group_id, batch_id: batch.batch_id },
    JSON.parse(JSON.stringify(batch)) as ManagedRecord["data"],
  );
}
for (const item of mockCheckpoints.items) {
  put(
    {
      kind: "checkpoint",
      group_id: item.group_id,
      date_str: item.date_str,
      stage_name: item.stage_name,
      trace_id: item.trace_id || "",
    },
    {
      checkpoint_id: item.checkpoint_id || "demo-checkpoint",
      group_id: item.group_id,
      date_str: item.date_str,
      stage_name: item.stage_name,
      trace_id: item.trace_id || "",
      created_at: item.created_at,
      data_size_bytes: item.data_size_bytes,
      expire_at: Math.floor(Date.now() / 1000) + 86400 * 30,
      data:
        item.stage_name === "STATS_ANALYSIS"
          ? { total_messages: 420, active_users: 23, total_characters: 6850 }
          : ["FETCH_MESSAGES", "CLEAN_MESSAGES"].includes(item.stage_name)
            ? {
                messages_count: 420,
                messages: [
                  { sender_id: "demo-user", text_content: "示例：讨论报告排版与字体管理。" },
                ],
              }
            : ["RENDER_REPORT", "COMIC_DRAWING"].includes(item.stage_name)
              ? { output_format: "png", template: "HatsuneMiku", note: "示例渲染产物记录" }
              : {
                  topics: [{ topic: "Typst 模板优化", detail: "讨论报告排版与字体按需管理。" }],
                  messages_count: 420,
                },
    },
  );
}
put(
  {
    kind: "history",
    key: "analysis_123456789_2026-11-03_12-00",
    group_id: "123456789",
    date_str: "2026-11-03",
  },
  {
    summary: { total_messages: 420, active_users: 23 },
    analysis: {
      topics: [
        { topic: "Typst 模板优化", contributors: ["未来"], detail: "完善模板排版和资源管理。" },
      ],
    },
  },
);
put(
  {
    kind: "history",
    key: "analysis_123456789_2026-11-02_12-00",
    group_id: "123456789",
    date_str: "2026-11-02",
  },
  { summary: { total_messages: 306, active_users: 18 }, analysis: { topics: [] } },
);
put(
  { kind: "avatar", key: "onebot:123456" },
  {
    data_uri:
      "data:image/svg+xml;base64," +
      btoa(
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120"><circle cx="60" cy="60" r="60" fill="#39c5bb"/></svg>',
      ),
  },
);

// 同一分钟的同号群存档保留独立版本，用于检查真实会话元数据。
for (const [index, platform] of ["aiocqhttp_main", "telegram_main"].entries()) {
  const key = `analysis_123456789_2026-11-07_12-00_${String(index + 1).padStart(32, "0")}`;
  put(
    { kind: "history", key, platform_id: platform, group_id: "123456789", date_str: "2026-11-07" },
    {
      platform_id: platform,
      group_id: "123456789",
      date_str: "2026-11-07",
      created_at: `2026-11-07T12:00:0${index}.000000`,
      summary: {
        message_count: 300 + index,
        participant_count: 12,
        generated_at: "2026-11-07 12:00:00",
      },
      analysis: {
        platform_id: platform,
        group_id: "123456789",
        trace_id: `demo-history-session-${index}`,
        topics: [{ topic: "示例：周末出游", detail: "展示同号群在不同接入下的独立历史版本。" }],
      },
    },
  );
}

// 使用独立示例存档补足跨页浏览，不冒充已经执行的分析任务。
for (let day = 1; day <= 24; day++) {
  const date = `2026-10-${String(day).padStart(2, "0")}`;
  const group = day % 2 ? "123456789" : "-1001987654321";
  put(
    { kind: "history", key: `analysis_${group}_${date}_12-00`, group_id: group, date_str: date },
    {
      demo: true,
      summary: { total_messages: 300 + day * 7, active_users: 12 + (day % 9) },
      analysis: {
        topics: [
          {
            topic: day % 2 ? "周末出游安排" : "做饭与摄影交流",
            detail: "示例存档，用于检查历史浏览、导出与修订。",
          },
        ],
      },
    },
  );
}
for (let index = 1; index <= 22; index++) {
  put(
    {
      kind: "avatar",
      key: `${index % 2 ? "telegram" : "discord"}:demo-user-${String(index).padStart(2, "0")}`,
    },
    {
      data_uri:
        "data:image/svg+xml;base64," +
        btoa(
          `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120"><rect width="120" height="120" rx="24" fill="#56768b"/><text x="60" y="73" text-anchor="middle" fill="white" font-size="36">${index}</text></svg>`,
        ),
    },
  );
}

export const managedRecordMockHandlers = {
  "GET plugin-data/records": (query?: Record<string, unknown>) => {
    const search = String(query?.search || "").toLocaleLowerCase();
    const items = [...records.values()]
      .filter(
        (record) =>
          record.locator.kind === query?.kind &&
          String(record.locator.key || "")
            .toLocaleLowerCase()
            .includes(search),
      )
      .sort((left, right) => {
        const a = left.locator.key || "",
          b = right.locator.key || "";
        return a === b ? 0 : a > b ? -1 : 1;
      });
    const start = (Number(query?.page || 1) - 1) * 20;
    return {
      status: "ok",
      data: {
        items: items.slice(start, start + 20).map((record) => ({
          locator: record.locator,
          name: record.locator.key || "",
          size_bytes: new TextEncoder().encode(JSON.stringify(record.data)).length,
        })),
        total: items.length,
      },
    };
  },
  "GET plugin-data/records/detail": (query?: Record<string, unknown>) => {
    const locator = query as RecordLocator;
    const record = records.get(recordKey(locator));
    return record
      ? { status: "ok", data: record }
      : { status: "error", message: "记录不存在或快照已过期" };
  },
  "POST plugin-data/records/mutate": (body?: Record<string, unknown>) => {
    const locator = body?.locator as RecordLocator;
    if (!locator) return { status: "error", message: "缺少定位字段" };
    const key = recordKey(locator),
      current = records.get(key);
    if (body?.operation === "create" ? !!current : !current || current.revision !== body?.revision)
      return { status: "error", message: "记录已变化，请刷新" };
    if (body?.operation === "delete") {
      records.delete(key);
      if (locator.kind === "batch") {
        const session = incrementalMockSession(locator.group_id || "", locator.platform_id || "");
        session.batches = session.batches.filter((item) => item.batch_id !== locator.batch_id);
      }
      if (locator.kind === "checkpoint") {
        mockCheckpoints.items = mockCheckpoints.items.filter(
          (item) =>
            recordKey({
              kind: "checkpoint",
              group_id: item.group_id,
              date_str: item.date_str,
              stage_name: item.stage_name,
              trace_id: item.trace_id || "",
            }) !== key,
        );
        mockCheckpoints.total = mockCheckpoints.items.length;
      }
    } else {
      put(locator, body?.data as ManagedRecord["data"]);
      if (locator.kind === "batch" && body?.data && typeof body.data === "object") {
        const data = body.data as Record<string, unknown>;
        const item = {
          group_id: locator.group_id || "",
          batch_id: locator.batch_id || "",
          timestamp: Number(data.timestamp || Date.now() / 1000),
          messages_count: Number(data.messages_count || 0),
          characters_count: Number(data.characters_count || 0),
          topics_count: Array.isArray(data.topics) ? data.topics.length : 0,
        };
        const session = incrementalMockSession(locator.group_id || "", locator.platform_id || "");
        const index = session.batches.findIndex(
          (batch) => batch.group_id === item.group_id && batch.batch_id === item.batch_id,
        );
        if (index >= 0)
          session.batches[index] = {
            ...session.batches[index],
            ...item,
          };
        else session.batches.push(item);
      }
    }
    return { status: "ok", data: { success: true } };
  },
};
