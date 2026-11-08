import type { HTMLAttributes } from "react";
import { IconAlertCircle, IconCircleCheck, IconInfoCircle } from "@tabler/icons-react";
import { cn } from "../lib/cn";

type AlertVariant = "info" | "success" | "warning" | "destructive";
const styles: Record<AlertVariant, string> = {
  info: "bg-info/10 text-info",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  destructive: "bg-destructive/10 text-destructive",
};
export function Alert({
  variant = "info",
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & { variant?: AlertVariant }) {
  const Icon =
    variant === "success" ? IconCircleCheck : variant === "info" ? IconInfoCircle : IconAlertCircle;
  return (
    <div
      role={variant === "destructive" ? "alert" : "status"}
      className={cn(
        "flex min-w-0 items-start gap-2 rounded-xl p-3 text-sm",
        styles[variant],
        className,
      )}
      {...props}
    >
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 break-words">{children}</div>
    </div>
  );
}
export function AlertDescription({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-1 leading-relaxed", className)} {...props} />;
}
