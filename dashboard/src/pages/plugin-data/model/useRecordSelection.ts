import { useCallback, useState } from "react";
import type { Key } from "react";
import {
  fetchManagedRecord,
  mutateManagedRecord,
  recordKey,
  type RecordLocator,
} from "../../../entities/plugin-data/api/managedRecordsApi";

export function useRecordSelection(locators: RecordLocator[], onChanged: () => void) {
  const [selected, setSelected] = useState<RecordLocator[]>([]);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<{
    deleted: number;
    failed: { name: string; message: string }[];
  } | null>(null);
  const select = (keys: Key[]) => {
    const known = new Map(
      [...selected, ...locators].map((locator) => [recordKey(locator), locator]),
    );
    setSelected(
      keys
        .slice(0, 200)
        .flatMap((key) => (known.get(String(key)) ? [known.get(String(key))!] : [])),
    );
  };
  const clear = useCallback(() => {
    setSelected([]);
    setResult(null);
  }, []);
  const remove = async (targets = selected) => {
    setBusy(true);
    setProgress(0);
    setResult(null);
    const failed: { name: string; message: string }[] = [];
    const deleted = new Set<string>();
    for (const locator of targets) {
      try {
        const record = await fetchManagedRecord(locator);
        await mutateManagedRecord({
          locator: record.locator,
          revision: record.revision,
          operation: "delete",
        });
        deleted.add(recordKey(locator));
      } catch (cause) {
        failed.push({
          name:
            locator.key ||
            locator.batch_id ||
            `${locator.group_id} ${locator.date_str} ${locator.stage_name}`,
          message: cause instanceof Error ? cause.message : "删除失败",
        });
      }
      setProgress((value) => value + 1);
    }
    setSelected((current) => current.filter((locator) => !deleted.has(recordKey(locator))));
    setResult({ deleted: deleted.size, failed });
    setBusy(false);
    onChanged();
  };
  return { selected, keys: selected.map(recordKey), select, busy, progress, result, remove, clear };
}

export { recordKey } from "../../../entities/plugin-data/api/managedRecordsApi";
