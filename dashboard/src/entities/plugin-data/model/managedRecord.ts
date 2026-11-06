import type { components } from "../../../shared/api/generated/schema";

type RecordLocator = components["schemas"]["RecordLocator"];
export function recordKey(locator: RecordLocator) {
  if (locator.kind === "history" || locator.kind === "avatar")
    return JSON.stringify([locator.kind, locator.key || ""]);
  return JSON.stringify([
    locator.kind,
    locator.group_id || "",
    locator.batch_id || "",
    locator.date_str || "",
    locator.stage_name || "",
    locator.trace_id || "",
  ]);
}
