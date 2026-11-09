import { cn } from "@/shared/lib/cn";

type ProgressProps = {
  value?: number | null;
  label: string;
  variant?: "default" | "info" | "success" | "warning" | "destructive";
  className?: string;
};
const styles = {
  default: "bg-primary",
  info: "bg-info",
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
};
export function Progress({ value, label, variant = "default", className }: ProgressProps) {
  // 未知、非有限进度保持不确定状态，不能伪造成零或已完成。
  const percent =
    typeof value === "number" && Number.isFinite(value)
      ? Math.min(100, Math.max(0, value))
      : undefined;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}
    >
      <div
        className={cn(
          "h-full rounded-full",
          styles[variant],
          percent === undefined && "animate-pulse motion-reduce:animate-none",
        )}
        style={{ width: percent === undefined ? "35%" : `${percent}%` }}
      />
    </div>
  );
}
