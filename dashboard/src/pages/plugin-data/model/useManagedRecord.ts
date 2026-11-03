import { useEffect, useRef, useState } from "react";
import { message } from "antd";
import { z } from "zod";
import { fetchManagedRecord, mutateManagedRecord, recordLocatorSchema, type ManagedRecord, type RecordLocator } from "../../../entities/plugin-data/api/managedRecordsApi";

export function useManagedRecord(locator: RecordLocator | null, onChanged: () => void, onClose: () => void, importKind?: string) {
  const [record, setRecord] = useState<ManagedRecord | null>(null);
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const locatorKey = JSON.stringify(locator);
  useEffect(() => {
    const ref = sequence;
    const request = ++ref.current;
    setRecord(null); setEditing(!!importKind); setError(""); setText(""); setBusy(false);
    if (importKind) {
      setText(JSON.stringify({ locator: { kind: importKind, ...(importKind === "batch" ? { group_id: "", batch_id: "" } : { key: "analysis_群号_2026-11-03_12-00" }) }, data: {}, revision: "" }, null, 2));
      return;
    }
    if (!locatorKey || locatorKey === "null") return;
    setBusy(true);
    void fetchManagedRecord(JSON.parse(locatorKey) as RecordLocator).then(value => {
      if (sequence.current === request) { setRecord(value); setText(JSON.stringify(value.data, null, 2)); }
    }).catch(cause => { if (sequence.current === request) setError(cause instanceof Error ? cause.message : "记录读取失败"); })
      .finally(() => { if (sequence.current === request) setBusy(false); });
    return () => { ref.current++; };
  }, [locatorKey, importKind]);

  const save = async (operation: "create" | "replace" | "delete") => {
    setBusy(true); setError("");
    try {
      const imported = importKind ? z.object({ locator: recordLocatorSchema, data: z.json() }).parse(JSON.parse(text)) : null;
      if (imported && imported.locator.kind !== importKind) throw new Error("导入类型与当前模块不一致");
      const target = imported?.locator || record?.locator;
      if (!target) throw new Error("请先读取记录");
      const data = operation === "delete" ? undefined : imported?.data ?? z.json().parse(JSON.parse(text));
      await mutateManagedRecord({ locator: target, data, operation, revision: record?.revision });
      void message.success("记录操作完成"); onChanged(); onClose();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "记录操作失败"); }
    finally { setBusy(false); }
  };
  const download = () => {
    if (!record) return;
    if (record.locator.kind === "avatar") {
      const data = record.data;
      const uri = data && typeof data === "object" && !Array.isArray(data) && "data_uri" in data ? data.data_uri : null;
      const format = typeof uri === "string" ? /^data:image\/(png|jpe?g|webp|gif|svg\+xml|bmp|x-icon);base64,/.exec(uri)?.[1] : null;
      if (!format || typeof uri !== "string") { void message.error("头像图片暂不可下载，请刷新后重试"); return; }
      const link = document.createElement("a"); link.href = uri;
      link.download = `avatar-${record.locator.key || "cache"}.${format === "svg+xml" ? "svg" : format === "x-icon" ? "ico" : format}`.replace(/[\\/:*?"<>|]/g, "_");
      link.click(); return;
    }
    const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url;
    link.download = `${record.locator.kind}-${record.locator.batch_id || record.locator.key || record.locator.date_str || "record"}.json`.replace(/[\\/:*?"<>|]/g, "_");
    link.click(); URL.revokeObjectURL(url);
  };
  return { record, text, setText, editing, setEditing, busy, error, save, download };
}
