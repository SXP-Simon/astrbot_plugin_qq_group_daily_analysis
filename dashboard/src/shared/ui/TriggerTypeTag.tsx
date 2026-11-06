import type { CSSProperties } from "react";
import { formatTriggerType } from "../lib/formatters";

export function TriggerTypeTag({
  triggerType,
  style,
}: {
  triggerType?: string;
  style?: CSSProperties;
}) {
  return (
    <span
      className="inline-flex rounded-lg bg-muted px-2 py-1 text-xs text-muted-foreground"
      style={style}
    >
      {formatTriggerType(triggerType).text}
    </span>
  );
}
