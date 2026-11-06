import { recordKey } from "../../entities/plugin-data/model/managedRecord";
import type {
  ManagedRecord,
  RecordLocator,
} from "../../entities/plugin-data/api/managedRecordsApi";
import { mockCheckpoints, mockIncrementalBatches } from "./pluginData";

let version = 0;
const records = new Map<string, ManagedRecord>();
function put(locator: RecordLocator, data: ManagedRecord["data"]) {
  const record = { locator, data, revision: `demo-${++version}` };
  records.set(recordKey(locator), record);
  return record;
}
for (const batch of mockIncrementalBatches.batches) {
  put(
    { kind: "batch", group_id: batch.group_id, batch_id: batch.batch_id },
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
      created_at: 1793664000,
      expire_at: 1796256000,
      data: {
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

export const managedRecordMockHandlers = {
  "GET plugin-data/records": (query?: Record<string, unknown>) => {
    const items = [...records.values()].filter(
      (record) =>
        record.locator.kind === query?.kind &&
        String(record.locator.key || "").includes(String(query?.search || "")),
    );
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
      if (locator.kind === "batch")
        mockIncrementalBatches.batches = mockIncrementalBatches.batches.filter(
          (item) => item.group_id !== locator.group_id || item.batch_id !== locator.batch_id,
        );
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
        const index = mockIncrementalBatches.batches.findIndex(
          (batch) => batch.group_id === item.group_id && batch.batch_id === item.batch_id,
        );
        if (index >= 0)
          mockIncrementalBatches.batches[index] = {
            ...mockIncrementalBatches.batches[index],
            ...item,
          };
        else mockIncrementalBatches.batches.push(item);
      }
    }
    return { status: "ok", data: { success: true } };
  },
};
