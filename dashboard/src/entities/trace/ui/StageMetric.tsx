import type { ReactNode } from "react";
import { IconAlertCircle } from "@tabler/icons-react";

interface StageMetricProps {
  label: string;
  value: ReactNode;
  isMono?: boolean;
  status?: "default" | "success" | "error" | "warning";
}

export function StageMetric({ label, value, isMono = true, status = "default" }: StageMetricProps) {
  return (
    <span className="flex min-w-0 flex-col gap-1 text-xs leading-relaxed">
      <span className="text-muted-foreground">{label}:</span>
      <span
        className={`flex min-w-0 items-start gap-1 break-words ${isMono ? "font-mono" : ""} ${status === "error" ? "text-destructive" : status === "warning" ? "text-warning" : "text-foreground"}`}
      >
        {status === "warning" || status === "error" ? (
          <IconAlertCircle
            className="mt-0.5 size-3.5 shrink-0"
            aria-label={status === "error" ? "异常" : "注意"}
          />
        ) : null}
        <span className="min-w-0 break-words">{value}</span>
      </span>
    </span>
  );
}
