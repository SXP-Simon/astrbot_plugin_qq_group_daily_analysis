import { IconActivity } from "@tabler/icons-react";
import { formatStageName } from "../../../shared/lib/formatters";

export function TaskStageBadge({ stage }: { stage: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-foreground">
      <IconActivity size={16} className="shrink-0 text-muted-foreground" aria-hidden="true" />
      {formatStageName(stage)}
    </span>
  );
}
