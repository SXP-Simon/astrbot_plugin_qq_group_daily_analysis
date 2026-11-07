import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import {
  fetchManagedRecord,
  mutateManagedRecord,
  recordLocatorSchema,
  recordKey,
  type ManagedRecord,
  type RecordLocator,
} from "../../../entities/plugin-data/api/managedRecordsApi";

export function useManagedRecord(
  locator: RecordLocator | null,
  onChanged: () => void,
  onClose: () => void,
  importKind?: string,
) {
  const [record, setRecord] = useState<ManagedRecord | null>(null);
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const mutation = useRef<number | null>(null);
  const [reload, setReload] = useState(0);
  const locatorKey = JSON.stringify(locator);
  useEffect(() => {
    const ref = sequence;
    const request = ++ref.current;
    setRecord(null);
    setEditing(!!importKind);
    setError("");
    setText("");
    setBusy(false);
    mutation.current = null;
    if (importKind) {
      setText(
        JSON.stringify(
          {
            locator: {
              kind: importKind,
              ...(importKind === "batch"
                ? { group_id: "", batch_id: "" }
                : { key: "analysis_群号_2026-11-03_12-00" }),
            },
            data: {},
            revision: "",
          },
          null,
          2,
        ),
      );
      return () => {
        ref.current++;
      };
    }
    if (!locatorKey || locatorKey === "null")
      return () => {
        ref.current++;
      };
    setBusy(true);
    void fetchManagedRecord(recordLocatorSchema.parse(JSON.parse(locatorKey)))
      .then((value) => {
        if (sequence.current === request) {
          if (
            recordKey(value.locator) !==
            recordKey(recordLocatorSchema.parse(JSON.parse(locatorKey)))
          )
            throw new Error("返回的记录与所选条目不一致，请重新读取");
          setRecord(value);
          setText(JSON.stringify(value.data, null, 2));
        }
      })
      .catch((cause) => {
        if (sequence.current === request)
          setError(cause instanceof Error ? cause.message : "记录读取失败");
      })
      .finally(() => {
        if (sequence.current === request) setBusy(false);
      });
    return () => {
      ref.current++;
    };
  }, [locatorKey, importKind, reload]);

  const save = async (operation: "create" | "replace" | "delete") => {
    if (busy || mutation.current !== null) return false;
    const request = sequence.current;
    mutation.current = request;
    setBusy(true);
    setError("");
    try {
      const imported = importKind
        ? z.object({ locator: recordLocatorSchema, data: z.json() }).parse(JSON.parse(text))
        : null;
      if (imported && imported.locator.kind !== importKind)
        throw new Error("导入类型与当前模块不一致");
      const target = imported?.locator || record?.locator;
      if (!target) throw new Error("请先读取记录");
      const data =
        operation === "delete"
          ? undefined
          : imported
            ? imported.data
            : z.json().parse(JSON.parse(text));
      await mutateManagedRecord({ locator: target, data, operation, revision: record?.revision });
      if (sequence.current !== request) return false;
      toast.success(
        operation === "delete"
          ? "记录已删除"
          : operation === "create"
            ? "记录已导入"
            : "修订已保存",
      );
      onChanged();
      onClose();
      return true;
    } catch (cause) {
      if (sequence.current === request)
        setError(
          cause instanceof SyntaxError
            ? "JSON 格式不正确，请检查后再保存。"
            : cause instanceof z.ZodError
              ? "记录格式不正确，请确认导入内容包含有效的 locator 和 data。"
              : cause instanceof Error
                ? cause.message
                : "记录操作失败",
        );
      return false;
    } finally {
      if (sequence.current === request) {
        mutation.current = null;
        setBusy(false);
      }
    }
  };
  const download = () => {
    if (!record) return;
    if (record.locator.kind === "avatar") {
      const data = record.data;
      const uri =
        data && typeof data === "object" && !Array.isArray(data) && "data_uri" in data
          ? data.data_uri
          : null;
      const format =
        typeof uri === "string"
          ? /^data:image\/(png|jpe?g|webp|gif|svg\+xml|bmp|x-icon);base64,/.exec(uri)?.[1]
          : null;
      if (!format || typeof uri !== "string") {
        toast.error("头像图片暂不可下载，请刷新后重试");
        return;
      }
      const link = document.createElement("a");
      link.href = uri;
      link.download =
        `avatar-${record.locator.key || "cache"}.${format === "svg+xml" ? "svg" : format === "x-icon" ? "ico" : format}`.replace(
          /[\\/:*?"<>|]/g,
          "_",
        );
      link.click();
      return;
    }
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(record, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download =
      `${record.locator.kind}-${record.locator.batch_id || record.locator.key || record.locator.date_str || "record"}.json`.replace(
        /[\\/:*?"<>|]/g,
        "_",
      );
    link.click();
    URL.revokeObjectURL(url);
  };
  return {
    record,
    text,
    setText,
    editing,
    setEditing,
    busy,
    error,
    save,
    download,
    retry: () => setReload((value) => value + 1),
  };
}
